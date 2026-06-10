import tiktoken
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from core.context_manager import get_live_messages, build_memory_block
from core.score_config import get_active_profile, get_active_profile_name

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def count_tokens(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def compute_score(session_id: str) -> dict:
    from config import CLAUDE_CONTEXT_WINDOW

    profile = get_active_profile()
    weights = profile["weights"]
    thresholds = profile["thresholds"]

    w_token = weights["token_pressure"]
    w_drift = weights["semantic_drift"]
    w_redun = weights["redundancy"]
    warn_threshold = thresholds["warn"]
    red_threshold  = thresholds["red"]

    live = get_live_messages(session_id, tail=50)
    memory_block = build_memory_block(session_id)
    full_text = memory_block + "\n".join(m["content"] for m in live)
    token_count = count_tokens(full_text)

    # Token pressure penalty
    token_ratio   = min(token_count / CLAUDE_CONTEXT_WINDOW, 1.0)
    token_penalty = round(token_ratio * w_token, 1)

    # Semantic drift penalty
    drift_penalty = 0.0
    user_msgs = [m["content"] for m in live if m["role"] == "user"]
    if len(user_msgs) >= 2:
        model = _get_model()
        origin = model.encode([user_msgs[0]])
        recent = model.encode([user_msgs[-1]])
        similarity = float(cosine_similarity(origin, recent)[0][0])
        drift_penalty = round((1.0 - similarity) * w_drift, 1)

    # Redundancy penalty
    redundancy_penalty = 0.0
    if len(live) >= 4:
        recent_words = [set(m["content"].lower().split()) for m in live[-4:]]
        overlaps = []
        for i in range(len(recent_words)):
            for j in range(i + 1, len(recent_words)):
                union = recent_words[i] | recent_words[j]
                if union:
                    overlap = len(recent_words[i] & recent_words[j]) / len(union)
                    overlaps.append(overlap)
        if overlaps:
            redundancy_penalty = round((sum(overlaps) / len(overlaps)) * w_redun, 1)

    score = round(max(0.0, 100 - token_penalty - drift_penalty - redundancy_penalty), 1)

    if score >= warn_threshold:
        status = "green"
        hint = None
    elif score >= red_threshold:
        status = "yellow"
        hint = "Context is getting crowded — consider /carry soon"
    else:
        status = "red"
        hint = "Context degraded — use /carry to continue in a fresh session"

    return {
        "score": score,
        "status": status,
        "hint": hint,
        "profile": get_active_profile_name(),
        "breakdown": {
            "token_pressure": {"score": round(w_token - token_penalty, 1), "max": w_token},
            "semantic_drift": {"score": round(w_drift - drift_penalty, 1), "max": w_drift},
            "redundancy":     {"score": round(w_redun - redundancy_penalty, 1), "max": w_redun},
        },
        "token_count": token_count,
        "context_window": CLAUDE_CONTEXT_WINDOW,
    }


def score_label(score: float) -> str:
    profile = get_active_profile()
    warn = profile["thresholds"]["warn"]
    red  = profile["thresholds"]["red"]
    if score >= warn:
        return f"🟢 Fresh ({score}/100)"
    elif score >= red:
        return f"🟡 Crowded ({score}/100)"
    else:
        return f"🔴 Degraded ({score}/100)"
