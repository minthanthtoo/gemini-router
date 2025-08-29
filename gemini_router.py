#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Router v6 (Multi-Tier: Fast / Quality / Balance)
"""

import os, json, time, argparse, asyncio, functools
from pathlib import Path
from collections import deque, defaultdict
import google.generativeai as genai

# -------------------------------
# Config & State Paths
# -------------------------------
ROLLING_WINDOW = 20
COOLDOWN_SECS = 60
RANK_PROMPT = "Say hi."

STATS_FILE = Path("model_stats.json")
STATE_FILE = Path("router_state.json")
COOLDOWN_FILE = Path("cooldowns.json")

# -------------------------------
# State Management
# -------------------------------
def load_json(path, default):
    if path.exists():
        try:
            return json.load(path.open())
        except:
            return default
    return default

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

def load_stats():
    raw = load_json(STATS_FILE, {})
    stats = defaultdict(lambda: deque(maxlen=ROLLING_WINDOW))
    for m, entries in raw.items():
        stats[m] = deque(entries, maxlen=ROLLING_WINDOW)
    return stats

def save_stats(stats):
    serial = {m: list(d) for m, d in stats.items()}
    save_json(STATS_FILE, serial)

def load_cooldowns(): return load_json(COOLDOWN_FILE, {})
def save_cooldowns(c): save_json(COOLDOWN_FILE, c)

def load_state(): return load_json(STATE_FILE, {"lock": None})
def save_state(s): save_json(STATE_FILE, s)

# -------------------------------
# API Keys & Model Discovery
# -------------------------------
def get_api_keys():
    keys = [v for k,v in os.environ.items() if k.startswith("GEMINI_API_KEY")]
    if not keys:
        raise RuntimeError("No GEMINI_API_KEY* env vars found")
    return keys

def get_available_models(api_key):
    genai.configure(api_key=api_key)
    models = genai.list_models()
    usable = []
    for m in models:
        if "generateContent" not in getattr(m, "supported_generation_methods", []):
            continue
        if any(bad in m.name.lower() for bad in ["tts", "image", "thinking", "exp", "gemma"]):
            continue
        usable.append(m.name)
    return usable

# -------------------------------
# Routing via call_model
# -------------------------------
def call_model(model, key, prompt, stats):
    genai.configure(api_key=key)
    start = time.time()
    m = genai.GenerativeModel(model)
    resp = m.generate_content(prompt)
    latency = time.time() - start
    max_tokens = getattr(resp, "max_output_tokens", 0)
    stats[model].append({"success": 1, "latency": latency, "max_tokens": max_tokens})
    save_stats(stats)
    return {"model": model, "latency": latency, "max_tokens": max_tokens, "response": getattr(resp, "text", str(resp))}

# -------------------------------
# Probing via call_model async
# -------------------------------
async def test_model_async(model, keys, stats):
    import asyncio
    loop = asyncio.get_event_loop()
    for key in keys:
        try:
            func = functools.partial(call_model, model, key, RANK_PROMPT, stats)
            result = await loop.run_in_executor(None, func)
            return model, result["latency"]
        except Exception:
            continue
    stats[model].append({"success": 0, "latency": 0, "max_tokens": 0})
    return model, None

async def rank_models_parallel(models=None):
    keys = get_api_keys()
    stats = load_stats()
    if models is None:
        models = get_available_models(keys[0])
    tasks = [test_model_async(m, keys, stats) for m in models]
    await asyncio.gather(*tasks)
    save_stats(stats)
    return stats

# -------------------------------
# Multi-Tier Assignment
# -------------------------------
def assign_multi_tiers(stats):
    metrics = {}
    for m, entries in stats.items():
        entries = list(entries)
        if not entries:
            metrics[m] = {"latency": float("inf"), "max_tokens":0, "success_rate":0}
            continue
        successes = sum(e["success"] for e in entries)
        total = len(entries)
        success_rate = successes / total if total else 0
        latencies = [e["latency"] for e in entries if e["latency"] > 0]
        avg_latency = sum(latencies)/len(latencies) if latencies else float("inf")
        max_tokens = max(e.get("max_tokens",0) for e in entries) if entries else 0
        metrics[m] = {"latency": avg_latency, "max_tokens": max_tokens, "success_rate": success_rate}

    def tier_rank(rank_list):
        n = len(rank_list)
        tiers = {}
        for i, (m, _) in enumerate(rank_list):
            if i < n*0.2: tiers[m] = "S"
            elif i < n*0.5: tiers[m] = "A"
            elif i < n*0.8: tiers[m] = "B"
            else: tiers[m] = "C"
        return tiers

    fast_rank = sorted(metrics.items(), key=lambda x: x[1]["latency"])
    quality_rank = sorted(metrics.items(), key=lambda x: -x[1]["max_tokens"])
    balance_rank = sorted(metrics.items(), key=lambda x: (1-x[1]["success_rate"])*1000 + x[1]["latency"] - x[1]["max_tokens"]*0.1)

    return {
        m: {
            "fast": tier_rank(fast_rank)[m],
            "quality": tier_rank(quality_rank)[m],
            "balance": tier_rank(balance_rank)[m],
        }
        for m in stats
    }

# -------------------------------
# Routing
# -------------------------------
def route_request(prompt):
    keys = get_api_keys()
    stats = load_stats()
    state = load_state()
    cooldowns = load_cooldowns()
    multi_tiers = assign_multi_tiers(stats)

    order = []
    if state.get("lock"):
        order.append(state["lock"])
    for tier in ["S","A","B","C"]:
        order.extend([m for m,t in multi_tiers.items() if multi_tiers[m]["balance"]==tier and m not in order])

    for model in order:
        if model in cooldowns and time.time() < cooldowns[model]:
            continue
        for key in keys:
            try:
                return call_model(model, key, prompt, stats)
            except Exception:
                cooldowns[model] = time.time() + COOLDOWN_SECS
                save_cooldowns(cooldowns)
                continue
    raise RuntimeError("No available model worked")

# -------------------------------
# CLI
# -------------------------------
def cmd_rank(args):
    print("↻ Probing unlocked models...")
    stats = asyncio.run(rank_models_parallel())
    multi_tiers = assign_multi_tiers(stats)
    print("\nRanked models (Fast / Quality / Balance tiers):")
    for m in multi_tiers:
        f, q, b = multi_tiers[m]["fast"], multi_tiers[m]["quality"], multi_tiers[m]["balance"]
        print(f"{m:45} fast={f}  quality={q}  balance={b}")

def cmd_tiers(args):
    stats = load_stats()
    multi_tiers = assign_multi_tiers(stats)
    print(json.dumps(multi_tiers, indent=2))

def cmd_stats(args):
    stats = load_stats()
    # Convert deque -> list for JSON
    serial = {m:list(d) for m,d in stats.items()}
    print(json.dumps(serial, indent=2))

def cmd_cooldowns(args):
    print(json.dumps(load_cooldowns(), indent=2))

def cmd_route(args):
    print(json.dumps(route_request(args.prompt), indent=2))

def cmd_lock(args):
    save_state({"lock": args.model})
    print(f"Locked to {args.model}")

def cmd_unlock(args):
    save_state({"lock": None})
    print("Unlocked")

def main():
    parser = argparse.ArgumentParser(description="Gemini Router Multi-Tier")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("rank").set_defaults(func=cmd_rank)
    sub.add_parser("tiers").set_defaults(func=cmd_tiers)
    sub.add_parser("stats").set_defaults(func=cmd_stats)
    sub.add_parser("cooldowns").set_defaults(func=cmd_cooldowns)

    r = sub.add_parser("route"); r.add_argument("prompt"); r.set_defaults(func=cmd_route)
    l = sub.add_parser("lock"); l.add_argument("model"); r.set_defaults(func=cmd_lock)
    sub.add_parser("unlock").set_defaults(func=cmd_unlock)

    args = parser.parse_args()
    if not getattr(args,"func",None):
        parser.print_help(); return
    args.func(args)

if __name__ == "__main__":
    main()
