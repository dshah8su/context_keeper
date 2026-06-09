# context_keeper

A middleware layer that retains, compresses, enriches, and measures conversation context for long-running Claude and ChatGPT sessions — with a live context health score and a `/carry` trigger to seamlessly continue in a fresh chat.

## Quick Start

```bash
git clone https://github.com/dshah8su/context_keeper
cd context_keeper
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env        # Add your API keys
streamlit run ui/app.py
```

## Features

- **Context Retention** — Compresses long conversations without losing key facts, decisions, or code
- **Context Enrichment** — Builds a progressive memory so responses improve over time
- **Relevance Score** — Live 0–100% health score with Green / Yellow / Red indicator
- **Carry-Forward** — `/carry` packages your entire session context and opens a fresh chat pre-loaded with it
- **Dual Provider** — Works with Claude (Anthropic) and ChatGPT (OpenAI)

## Setup

1. Copy `.env.example` to `.env`
2. Add your `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`
3. Run `streamlit run ui/app.py`

See [REQUIREMENTS.md](REQUIREMENTS.md) for full project spec.
