# context_keeper — Project Requirements

## Project Overview

**context_keeper** is a middleware layer that sits between the user and AI providers (Claude & ChatGPT) to solve the context degradation problem in long-running conversations. It retains, compresses, enriches, and measures conversation context — and lets users carry that context into a fresh chat session without losing momentum.

---

## Problem Statement

Both Claude (200k token window) and ChatGPT (128k token window) silently degrade as conversations grow:
- Old messages get pushed out or deprioritized
- The model loses track of earlier decisions, entities, and facts
- Quality drops with no visible signal to the user
- Starting a new chat loses all accumulated context

---

## Requirement Pillars

---

### R1 — Context Retention & Compression

**Goal:** Preserve meaning across long conversations by compressing history without losing key information.

| # | Requirement | Priority |
|---|---|---|
| R1.1 | Summarize old conversation chunks into compressed memory blocks | Must Have |
| R1.2 | Extract and store named entities (people, topics, decisions, variables, code) | Must Have |
| R1.3 | Inject a structured memory block into every new API call | Must Have |
| R1.4 | Preserve code snippets and technical state verbatim (no lossy compression on code) | Must Have |
| R1.5 | Track open questions and unresolved threads separately | Should Have |
| R1.6 | Support configurable compression aggressiveness (light / balanced / aggressive) | Nice to Have |

---

### R2 — Context Enrichment

**Goal:** Make responses *better* as conversations progress, not worse.

| # | Requirement | Priority |
|---|---|---|
| R2.1 | Build a progressive knowledge graph per session (topics → subtopics → facts) | Must Have |
| R2.2 | Track user preferences stated in conversation (tone, format, domain language) | Must Have |
| R2.3 | Tag and index decisions made during the session | Must Have |
| R2.4 | Feed enriched context back into provider calls to improve response quality | Must Have |
| R2.5 | Detect topic shifts and update the active context accordingly | Should Have |

---

### R3 — Context Relevance Score

**Goal:** Give users a real-time signal of context health so they know when to act.

| # | Requirement | Priority |
|---|---|---|
| R3.1 | Compute a 0–100% context health score after each message | Must Have |
| R3.2 | Score factors: Token Pressure (40%), Semantic Drift (35%), Redundancy Ratio (25%) | Must Have |
| R3.3 | Display score visually: Green (80–100%), Yellow (50–79%), Red (0–49%) | Must Have |
| R3.4 | Surface a hint at configurable threshold (default 70%): *"Good point to start a new thread"* | Must Have |
| R3.5 | Show per-factor breakdown so user understands why score dropped | Should Have |
| R3.6 | Log score history per session for trend visualization | Nice to Have |

**Score Formula:**
```
Score = 100 − token_penalty − drift_penalty − redundancy_penalty

token_penalty     = (tokens_used / context_window)          × weight_token_pressure   [default 40]
drift_penalty     = cosine_distance(origin_emb, latest_emb) × weight_semantic_drift   [default 35]
redundancy_penalty= avg_word_overlap(last 4 messages)        × weight_redundancy       [default 25]
```

**Factor Breakdown:**

| Factor | Max Penalty | How It's Measured | What Triggers It |
|---|---|---|---|
| Token Pressure | 40 pts | `tokens_used / 200,000 × 40` | Context window filling up |
| Semantic Drift | 35 pts | Cosine distance between first & latest user message embeddings (`all-MiniLM-L6-v2`) | Topic changed significantly |
| Redundancy | 25 pts | Average word-overlap ratio across last 4 messages | Going in circles |

**Status Bands (configurable thresholds):**

| Score | Status | Signal |
|---|---|---|
| 80–100 | 🟢 Fresh | All good |
| 50–79 | 🟡 Crowded | Hint: "Consider /carry soon" |
| 0–49 | 🔴 Degraded | Warning: "Use /carry now" |

**Real-world Score Progression Example:**

| Message # | Token Penalty | Drift Penalty | Redundancy Penalty | Score |
|---|---|---|---|---|
| 5 | -2 | -0 | -0 | 98 🟢 |
| 25 | -8 | -5 | -3 | 84 🟢 |
| 60 | -18 | -12 | -8 | 62 🟡 |
| 100 | -30 | -20 | -15 | 35 🔴 |

---

### R3-CONFIG — Score Configuration Mechanism

**Goal:** Allow factor weights and thresholds to be adjusted at runtime without touching code — for testing, tuning, and personalisation.

| # | Requirement | Priority |
|---|---|---|
| R3-C.1 | All score weights stored in `scoring_config.json` (editable file) | Must Have |
| R3-C.2 | Weights must always sum to 100 — validation enforced on load | Must Have |
| R3-C.3 | Status band thresholds (`warn`, `red`) configurable per profile | Must Have |
| R3-C.4 | Named profiles supported (e.g. `default`, `technical`, `creative`, `strict`) | Must Have |
| R3-C.5 | Active profile switchable via MCP tool `ck_set_profile` without restart | Must Have |
| R3-C.6 | `reset` command restores factory defaults | Should Have |
| R3-C.7 | Each profile change is logged with timestamp for audit trail | Nice to Have |

**Config File Structure (`scoring_config.json`):**
```json
{
  "active_profile": "default",
  "profiles": {
    "default": {
      "weights": {
        "token_pressure": 40,
        "semantic_drift": 35,
        "redundancy":     25
      },
      "thresholds": {
        "warn": 70,
        "red":  50
      }
    },
    "technical": {
      "weights": { "token_pressure": 50, "semantic_drift": 20, "redundancy": 30 },
      "thresholds": { "warn": 75, "red": 55 }
    },
    "creative": {
      "weights": { "token_pressure": 25, "semantic_drift": 50, "redundancy": 25 },
      "thresholds": { "warn": 65, "red": 40 }
    },
    "strict": {
      "weights": { "token_pressure": 35, "semantic_drift": 35, "redundancy": 30 },
      "thresholds": { "warn": 80, "red": 60 }
    }
  }
}
```

**Profile Use Cases:**

| Profile | Best For | Why weights differ |
|---|---|---|
| `default` | General use | Balanced across all three factors |
| `technical` | Coding / debugging sessions | Token pressure matters more; drift less (topic stays focused) |
| `creative` | Brainstorming / writing | Drift is expected and OK; redundancy is the real warning sign |
| `strict` | Research / long documents | Tighter thresholds, earlier warnings |

---

### R4 — Carry-Forward Trigger

**Goal:** Let users seamlessly move a conversation to a new chat without losing context.

| # | Requirement | Priority |
|---|---|---|
| R4.1 | User triggers carry-forward via `/carry` command or UI button | Must Have |
| R4.2 | System generates a structured handoff block (summary + facts + topic state + open questions) | Must Have |
| R4.3 | Handoff block is injected as the system prompt of a new session | Must Have |
| R4.4 | New session opens pre-loaded and ready to continue | Must Have |
| R4.5 | User can edit/review the handoff block before confirming | Should Have |
| R4.6 | Carry-forward works across providers (Claude → Claude, GPT → GPT, Claude → GPT) | Should Have |

**Handoff Block Structure:**
```
[CONTEXT SUMMARY]       ← compressed history narrative
[KEY FACTS & ENTITIES]  ← extracted knowledge (bullet list)
[DECISIONS MADE]        ← decisions taken during session
[CURRENT TOPIC STATE]   ← what was being worked on last
[OPEN QUESTIONS]        ← unresolved threads to pick up
```

---

### R5 — Dual Provider Support

**Goal:** Work identically with Claude (Anthropic) and ChatGPT (OpenAI).

| # | Requirement | Priority |
|---|---|---|
| R5.1 | Support Anthropic Claude via `anthropic` SDK | Must Have |
| R5.2 | Support OpenAI ChatGPT via `openai` SDK | Must Have |
| R5.3 | Provider-agnostic core logic (memory layer doesn't care which model is used) | Must Have |
| R5.4 | Per-provider token counting (tiktoken for OpenAI, Anthropic tokenizer for Claude) | Must Have |
| R5.5 | User can switch providers mid-project (not mid-session) | Should Have |

---

## Tech Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Language | Python | 3.11+ | Core runtime |
| Claude API | `anthropic` | ≥0.49.0 | Claude provider |
| ChatGPT API | `openai` | ≥1.76.0 | OpenAI provider |
| UI | `streamlit` | ≥1.45.0 | Web chat interface + score dashboard |
| Token counting | `tiktoken` | ≥0.9.0 | OpenAI-side token measurement |
| Semantic scoring | `sentence-transformers` | ≥3.4.0 | Embedding-based drift detection |
| Environment | `python-dotenv` | ≥1.1.0 | API key management |
| CLI output | `rich` | ≥14.0.0 | Terminal formatting |
| Storage | SQLite3 | built-in | Sessions, messages, memory snapshots |

---

## Project Structure

```
context_keeper/
├── core/
│   ├── __init__.py
│   ├── context_manager.py    # Compression, storage, memory injection
│   ├── relevance_scorer.py   # Token %, semantic drift, density score
│   └── carry_forward.py      # Packages context for new session
├── providers/
│   ├── __init__.py
│   ├── claude.py             # Anthropic API wrapper
│   └── chatgpt.py            # OpenAI API wrapper
├── ui/
│   ├── __init__.py
│   └── app.py                # Streamlit web UI
├── storage/
│   └── sessions.db           # SQLite database (git-ignored)
├── .env                      # API keys (git-ignored)
├── .env.example              # Key template (committed)
├── .gitignore
├── config.py                 # Thresholds, model names, defaults
├── main.py                   # CLI entry point
├── requirements.txt
├── REQUIREMENTS.md           # This file
└── README.md
```

---

## Pre-Build Checklist

- [x] Python 3.12.10 installed
- [x] pip 25.0.1 available
- [x] git 2.53.0 installed
- [x] GitHub CLI (gh) authenticated as dshah8su
- [ ] `ANTHROPIC_API_KEY` added to `.env`
- [ ] `OPENAI_API_KEY` added to `.env`
- [ ] Python virtual environment created (`venv/`)
- [ ] All pip packages installed successfully

---

## Build Phases

| Phase | Scope | Status |
|---|---|---|
| 0 | Environment setup, GitHub repo, folder structure | In Progress |
| 1 | `context_manager.py` — core memory layer | Pending |
| 2 | `relevance_scorer.py` — score engine | Pending |
| 3 | Provider wrappers (Claude + ChatGPT) | Pending |
| 4 | Streamlit UI with live score dashboard | Pending |
| 5 | `/carry` trigger and handoff system | Pending |

---

## Success Criteria

- Conversations of 50+ exchanges maintain coherent, high-quality responses
- Context score accurately reflects conversation health (validated manually)
- `/carry` produces a handoff that allows a new session to continue without re-explaining context
- Works identically with Claude and ChatGPT
- Zero hardcoded API keys anywhere in the codebase
