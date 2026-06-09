from dotenv import load_dotenv
import os

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")

CLAUDE_MODEL  = "claude-sonnet-4-6"
OPENAI_MODEL  = "gpt-4o"

CLAUDE_CONTEXT_WINDOW  = 200_000
OPENAI_CONTEXT_WINDOW  = 128_000

SCORE_WARN_THRESHOLD   = 70   # yellow hint shown below this
SCORE_RED_THRESHOLD    = 50   # red warning shown below this

COMPRESSION_CHUNK_SIZE = 20   # compress after every N messages
