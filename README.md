# Gemini Router v0.1 (Multi-Tier: Fast / Quality / Balance) — Fully Fixed + Key Rotation

A **Python-based routing system** for Google Gemini Generative Models with **multi-tier model assignment**, **API key rotation**, **rolling statistics**, and **async probing**. Ideal for developers who need a resilient and automated way to route prompts to the best-performing Gemini model.

## Table of Contents

- [Features](#features)  
- [Installation](#installation)  
- [Configuration](#configuration)  
- [Usage](#usage)  
  - [CLI Commands](#cli-commands)  
- [Architecture](#architecture)  
- [Tier Assignment Logic](#tier-assignment-logic)  
- [API Key Rotation](#api-key-rotation)  
- [Async Probing](#async-probing)  
- [State Management](#state-management)  
- [Contributing](#contributing)  
- [License](#license)  

## Features

- ✅ Multi-tier model assignment: **Fast / Quality / Balance**  
- ✅ Rolling stats for latency, success rate, and token usage  
- ✅ API key rotation to prevent rate-limit failures  
- ✅ Async probing of unlocked models for performance ranking  
- ✅ Persistent state across sessions (`stats`, `cooldowns`, `router_state`)  
- ✅ CLI commands for probing, routing, locking, and diagnostics  
- ✅ Thread-safe JSON read/write operations  

## Installation

1. **Clone the repository**:

```bash
git clone https://github.com/minthanthtoo/gemini-router.git
cd gemini-router
```
	2.	Install dependencies:
```
pip install -r requirements.txt
```
Dependencies:
	•	Python ≥ 3.10
	•	google-generativeai
	•	asyncio
	•	tqdm (optional, for progress visualization)

Configuration

1. Set API Keys

Set one or more Gemini API keys in environment variables:

```
export GEMINI_API_KEY_1="your_api_key_1"
export GEMINI_API_KEY_2="your_api_key_2"
# ... add as many keys as needed
```

2. Optional Configs
	•	ROLLING_WINDOW: Number of recent entries to track per model (default 20)
	•	COOLDOWN_SECS: Seconds to cooldown failed models (default 60)
	•	STATS_FILE, STATE_FILE, COOLDOWN_FILE: JSON files to store persistent data

Usage

Run the main CLI script:

```
python gemini_router.py <command> [options]
```

CLI Commands

Command	Description
rank	Probe all unlocked models and update stats
tiers	Display Fast / Quality / Balance tier assignments
stats	Show raw rolling stats for all models
cooldowns	Show current model cooldowns
route <prompt>	Route a prompt to the best available model
lock <model>	Lock router to a specific model
unlock	Unlock the router from a locked model

Example:
```
python gemini_router.py rank
python gemini_router.py tiers
python gemini_router.py route "Write a short story about AI in space"
python gemini_router.py lock models/gemini-2.0-flash-lite
python gemini_router.py unlock
```

Architecture
	1.	State Management
	•	Persistent JSON files (stats, cooldowns, router_state)
	•	Thread-safe read/write operations
	2.	API Key Rotation
	•	Sequentially attempts all configured keys per model until success
	•	Updates cooldowns for failed models
	3.	Async Probing
	•	Uses asyncio + ThreadPoolExecutor to test all models concurrently
	•	Collects latency and success rate stats
	4.	Multi-Tier Assignment
	•	Assigns models to Fast / Quality / Balance tiers
	•	Metrics used: latency, max_tokens, success_rate
	•	Tiering is dynamically updated based on rolling stats

Tier Assignment Logic

Tier	Criteria
S	Top 20% models based on metric (latency / max tokens / balance)
A	Next 30%
B	Next 30%
C	Bottom 20%

Balance Metric Formula:

balance_score = (1 - success_rate)*1000 + latency - max_tokens*0.1

	•	Combines latency, max output tokens, and success rate into a single score

API Key Rotation
	•	Iterates through all available API keys for a given model
	•	Updates stats and cooldowns on failure
	•	Ensures robust routing even under rate-limit constraints

Async Probing
	•	Concurrently probes all unlocked models using asyncio
	•	Collects latency and success data for tier assignment
	•	Can be run manually via python gemini_router.py rank

State Management

Files used to persist data:
	•	model_stats.json → Rolling stats for all models
	•	cooldowns.json → Cooldown timestamps for failed models
	•	router_state.json → Current router lock state

All files are automatically created and updated. Thread-safe operations ensure consistent state under parallel execution.

Contributing
	1.	Fork the repository
	2.	Create a feature branch: git checkout -b feature-name
	3.	Commit changes: git commit -m "Add feature"
	4.	Push to branch: git push origin feature-name
	5.	Open a Pull Request

Ideas for Contributions:
	•	Add normalized tier scoring
	•	Support async API key rotation
	•	Implement logging and monitoring dashboards
	•	Add unit tests for routing and tier logic

License

MIT License © 2025 Min Thant Htoo


