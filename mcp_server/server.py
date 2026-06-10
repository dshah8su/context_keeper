import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from core.context_manager import init_db, create_session, save_message, build_memory_block
from core.relevance_scorer import compute_score, score_label
from core.carry_forward import generate_handoff
from core.score_config import (
    list_profiles, set_active_profile, upsert_profile,
    reset_to_defaults, get_active_profile_name
)

init_db()
mcp = FastMCP("context_keeper")


# ── Conversation tools ────────────────────────────────────────────────────────

@mcp.tool()
def ck_new_session(session_id: str) -> str:
    """Start a new context_keeper session."""
    create_session(session_id)
    profile = get_active_profile_name()
    return f"Session '{session_id}' created. Active scoring profile: '{profile}'"


@mcp.tool()
def ck_save_turn(session_id: str, user_message: str, assistant_message: str) -> str:
    """Save a full conversation turn (user + assistant) to memory."""
    save_message(session_id, "user", user_message)
    save_message(session_id, "assistant", assistant_message)
    data = compute_score(session_id)
    label = score_label(data["score"])
    hint = f"\n⚠️  {data['hint']}" if data["hint"] else ""
    return f"Turn saved. Context health: {label}{hint}"


@mcp.tool()
def ck_get_context(session_id: str) -> str:
    """Get the enriched memory block to prepend before sending a message to Claude."""
    create_session(session_id)
    memory = build_memory_block(session_id)
    return memory if memory else "No compressed memory yet — conversation is still fresh."


@mcp.tool()
def ck_get_score(session_id: str) -> str:
    """Get the full context health score and per-factor breakdown for a session."""
    data = compute_score(session_id)
    bd = data["breakdown"]
    lines = [
        f"Context Health : {score_label(data['score'])}",
        f"Active profile : {data['profile']}",
        f"Token usage    : {data['token_count']:,} / {data['context_window']:,}",
        f"",
        f"Breakdown:",
        f"  Token pressure  {bd['token_pressure']['score']:.1f} / {bd['token_pressure']['max']}",
        f"  Semantic drift  {bd['semantic_drift']['score']:.1f} / {bd['semantic_drift']['max']}",
        f"  Redundancy      {bd['redundancy']['score']:.1f} / {bd['redundancy']['max']}",
    ]
    if data["hint"]:
        lines.append(f"\n💡 {data['hint']}")
    return "\n".join(lines)


@mcp.tool()
def ck_carry_forward(session_id: str) -> str:
    """Generate a carry-forward handoff block to continue this session in a new chat."""
    return generate_handoff(session_id)


# ── Scoring config tools ──────────────────────────────────────────────────────

@mcp.tool()
def ck_list_profiles() -> str:
    """List all scoring profiles and show which one is active."""
    profiles = list_profiles()
    lines = []
    for name, p in profiles.items():
        active_marker = " ◀ ACTIVE" if p["active"] else ""
        w = p["weights"]
        t = p["thresholds"]
        lines.append(
            f"\n[{name}]{active_marker}\n"
            f"  {p['description']}\n"
            f"  Weights   → token_pressure:{w['token_pressure']}  "
            f"semantic_drift:{w['semantic_drift']}  redundancy:{w['redundancy']}\n"
            f"  Thresholds → warn:{t['warn']}  red:{t['red']}"
        )
    return "\n".join(lines)


@mcp.tool()
def ck_set_profile(profile_name: str) -> str:
    """Switch the active scoring profile (default / technical / creative / strict)."""
    return set_active_profile(profile_name)


@mcp.tool()
def ck_create_profile(
    name: str,
    weight_token_pressure: int,
    weight_semantic_drift: int,
    weight_redundancy: int,
    threshold_warn: int,
    threshold_red: int,
    description: str = ""
) -> str:
    """Create or update a custom scoring profile. Weights must sum to 100."""
    weights = {
        "token_pressure": weight_token_pressure,
        "semantic_drift": weight_semantic_drift,
        "redundancy":     weight_redundancy,
    }
    thresholds = {"warn": threshold_warn, "red": threshold_red}
    return upsert_profile(name, weights, thresholds, description)


@mcp.tool()
def ck_reset_config() -> str:
    """Reset all scoring profiles to factory defaults."""
    return reset_to_defaults()


if __name__ == "__main__":
    mcp.run()
