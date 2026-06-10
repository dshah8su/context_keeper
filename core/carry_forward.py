import anthropic
from core.context_manager import get_memory_snapshots, get_live_messages


def generate_handoff(session_id: str) -> str:
    from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

    snapshots = get_memory_snapshots(session_id)
    live = get_live_messages(session_id, tail=20)

    all_facts = []
    all_decisions = []
    summaries = []
    for snap in snapshots:
        summaries.append(snap["summary"])
        all_facts.extend(snap["facts"])
        all_decisions.extend(snap["decisions"])

    recent_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in live[-6:]
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""Generate a structured carry-forward handoff block from this conversation history.
This will be injected as a system prompt so a new session can continue seamlessly.

Previous summaries:
{chr(10).join(summaries) if summaries else "None yet"}

Established facts:
{chr(10).join(f"- {f}" for f in all_facts) if all_facts else "None"}

Decisions made:
{chr(10).join(f"- {d}" for d in all_decisions) if all_decisions else "None"}

Most recent exchanges:
{recent_text}

Use this exact format:

[CONTEXT SUMMARY]
<2-3 sentence narrative>

[KEY FACTS & ENTITIES]
<bullet list>

[DECISIONS MADE]
<bullet list>

[CURRENT TOPIC STATE]
<what was being worked on>

[OPEN QUESTIONS]
<unresolved threads>"""

    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    handoff = resp.content[0].text.strip()

    return (
        "You are continuing a conversation. Full context from the previous session:\n\n"
        + handoff
        + "\n\nAcknowledge you have the context and are ready to continue."
    )
