import sqlite3
import json
import re
from pathlib import Path
import anthropic

DB_PATH = Path(__file__).parent.parent / "storage" / "sessions.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TEXT DEFAULT (datetime('now')),
            provider TEXT DEFAULT 'claude',
            total_messages INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            is_compressed INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS memory_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            facts TEXT DEFAULT '[]',
            decisions TEXT DEFAULT '[]',
            msg_start INTEGER NOT NULL,
            msg_end INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
    """)
    conn.commit()
    conn.close()


def create_session(session_id: str, provider: str = "claude") -> str:
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO sessions (id, provider) VALUES (?, ?)",
        (session_id, provider)
    )
    conn.commit()
    conn.close()
    return session_id


def save_message(session_id: str, role: str, content: str) -> int:
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO sessions (id) VALUES (?)", (session_id,))
    cur = conn.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    msg_id = cur.lastrowid
    conn.execute(
        "UPDATE sessions SET total_messages = total_messages + 1 WHERE id = ?",
        (session_id,)
    )
    conn.commit()
    conn.close()
    _compress_if_needed(session_id)
    return msg_id


def get_live_messages(session_id: str, tail: int = 10) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT role, content FROM messages
           WHERE session_id = ? AND is_compressed = 0
           ORDER BY id DESC LIMIT ?""",
        (session_id, tail)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def get_memory_snapshots(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT summary, facts, decisions FROM memory_snapshots WHERE session_id = ? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    return [
        {
            "summary": r["summary"],
            "facts": json.loads(r["facts"]),
            "decisions": json.loads(r["decisions"])
        }
        for r in rows
    ]


def build_memory_block(session_id: str) -> str:
    snapshots = get_memory_snapshots(session_id)
    if not snapshots:
        return ""
    lines = ["=== CONVERSATION MEMORY (compressed history) ==="]
    for i, snap in enumerate(snapshots, 1):
        lines.append(f"\n[Block {i}] {snap['summary']}")
        if snap["facts"]:
            lines.append("Facts: " + " | ".join(snap["facts"]))
        if snap["decisions"]:
            lines.append("Decisions: " + " | ".join(snap["decisions"]))
    lines.append("\n=== END MEMORY ===\n")
    return "\n".join(lines)


def get_uncompressed_count(session_id: str) -> int:
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id = ? AND is_compressed = 0",
        (session_id,)
    ).fetchone()[0]
    conn.close()
    return count


def _compress_if_needed(session_id: str):
    from config import COMPRESSION_CHUNK_SIZE
    count = get_uncompressed_count(session_id)
    if count < COMPRESSION_CHUNK_SIZE:
        return

    conn = get_conn()
    # Keep last 5 messages live; compress everything before that
    rows = conn.execute(
        """SELECT id, role, content FROM messages
           WHERE session_id = ? AND is_compressed = 0
           ORDER BY id LIMIT ?""",
        (session_id, count - 5)
    ).fetchall()
    conn.close()

    if not rows:
        return

    messages_to_compress = [{"role": r["role"], "content": r["content"]} for r in rows]
    ids_to_compress = [r["id"] for r in rows]
    summary_data = _call_claude_compress(messages_to_compress)

    conn = get_conn()
    conn.execute(
        """INSERT INTO memory_snapshots
           (session_id, summary, facts, decisions, msg_start, msg_end)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            summary_data["summary"],
            json.dumps(summary_data["facts"]),
            json.dumps(summary_data["decisions"]),
            ids_to_compress[0],
            ids_to_compress[-1],
        )
    )
    placeholders = ",".join("?" * len(ids_to_compress))
    conn.execute(
        f"UPDATE messages SET is_compressed = 1 WHERE id IN ({placeholders})",
        ids_to_compress
    )
    conn.commit()
    conn.close()


def _call_claude_compress(messages: list[dict]) -> dict:
    from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )
    prompt = f"""Compress the following conversation into a structured memory block.

Respond ONLY with valid JSON in this exact format:
{{
  "summary": "2-4 sentence narrative of what was discussed",
  "facts": ["fact1", "fact2"],
  "decisions": ["decision1"]
}}

Conversation:
{conversation_text}"""

    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"summary": text[:500], "facts": [], "decisions": []}
