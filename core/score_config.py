import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "scoring_config.json"

FACTORY_DEFAULTS = {
    "active_profile": "default",
    "profiles": {
        "default": {
            "description": "Balanced across all three factors",
            "weights": {"token_pressure": 40, "semantic_drift": 35, "redundancy": 25},
            "thresholds": {"warn": 70, "red": 50},
        },
        "technical": {
            "description": "For coding/debugging — token pressure weighted higher",
            "weights": {"token_pressure": 50, "semantic_drift": 20, "redundancy": 30},
            "thresholds": {"warn": 75, "red": 55},
        },
        "creative": {
            "description": "For brainstorming — drift expected, redundancy is the signal",
            "weights": {"token_pressure": 25, "semantic_drift": 50, "redundancy": 25},
            "thresholds": {"warn": 65, "red": 40},
        },
        "strict": {
            "description": "For research — tighter thresholds, earlier warnings",
            "weights": {"token_pressure": 35, "semantic_drift": 35, "redundancy": 30},
            "thresholds": {"warn": 80, "red": 60},
        },
    },
}


def _load() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return FACTORY_DEFAULTS.copy()


def _save(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def _validate_weights(weights: dict) -> str | None:
    required = {"token_pressure", "semantic_drift", "redundancy"}
    if set(weights.keys()) != required:
        return f"Weights must contain exactly: {required}"
    total = sum(weights.values())
    if total != 100:
        return f"Weights must sum to 100, got {total}"
    if any(v < 0 for v in weights.values()):
        return "All weights must be non-negative"
    return None


def get_active_profile() -> dict:
    cfg = _load()
    name = cfg.get("active_profile", "default")
    profiles = cfg.get("profiles", {})
    return profiles.get(name, FACTORY_DEFAULTS["profiles"]["default"])


def get_active_profile_name() -> str:
    return _load().get("active_profile", "default")


def list_profiles() -> dict:
    cfg = _load()
    result = {}
    active = cfg.get("active_profile", "default")
    for name, profile in cfg.get("profiles", {}).items():
        result[name] = {
            "description": profile.get("description", ""),
            "weights": profile["weights"],
            "thresholds": profile["thresholds"],
            "active": name == active,
        }
    return result


def set_active_profile(name: str) -> str:
    cfg = _load()
    if name not in cfg.get("profiles", {}):
        available = list(cfg.get("profiles", {}).keys())
        return f"Profile '{name}' not found. Available: {available}"
    cfg["active_profile"] = name
    _save(cfg)
    return f"Active profile set to '{name}'"


def upsert_profile(name: str, weights: dict, thresholds: dict, description: str = "") -> str:
    err = _validate_weights(weights)
    if err:
        return f"Invalid weights: {err}"
    if "warn" not in thresholds or "red" not in thresholds:
        return "Thresholds must include 'warn' and 'red' keys"
    if thresholds["warn"] <= thresholds["red"]:
        return "'warn' threshold must be higher than 'red' threshold"

    cfg = _load()
    cfg.setdefault("profiles", {})[name] = {
        "description": description,
        "weights": weights,
        "thresholds": thresholds,
    }
    _save(cfg)
    return f"Profile '{name}' saved successfully"


def reset_to_defaults() -> str:
    _save(FACTORY_DEFAULTS.copy())
    return "Scoring config reset to factory defaults"
