MOOD_MAP = {
    "amazing": 5.0, "wonderful": 5.0, "fantastic": 5.0, "great": 5.0, "incredible": 5.0,
    "happy": 4.5, "good": 4.0, "pretty good": 4.0, "excited": 4.5, "grateful": 4.5,
    "fine": 3.5, "okay": 3.0, "ok": 3.0, "meh": 3.0, "alright": 3.0, "so-so": 3.0,
    "tired": 2.5, "exhausted": 2.0, "drained": 2.0, "sleepy": 2.5,
    "anxious": 2.0, "worried": 2.0, "nervous": 2.0, "stressed": 2.0, "overwhelmed": 1.5,
    "sad": 1.5, "down": 1.5, "lonely": 1.5, "blue": 1.5, "upset": 1.5,
    "rough": 1.0, "terrible": 1.0, "awful": 1.0, "horrible": 1.0, "miserable": 1.0,
    "crying": 1.0, "hopeless": 0.5, "scared": 1.5,
}


def detect_mood_keyword(text: str) -> tuple[str, float] | None:
    """Try to detect mood from keywords in text. Returns (mood_label, score) or None."""
    lower = text.lower()
    # Check longer phrases first to avoid partial matches
    for word in sorted(MOOD_MAP.keys(), key=len, reverse=True):
        if word in lower:
            return (word, MOOD_MAP[word])
    return None


def calculate_trend(moods: list[dict], window: int = 7) -> str:
    """Analyze recent mood entries. Returns 'improving', 'stable', or 'declining'."""
    if len(moods) < 3:
        return "stable"
    scores = [m["mood_score"] for m in moods[-window:]]
    mid = len(scores) // 2
    first_half = sum(scores[:mid]) / mid
    second_half = sum(scores[mid:]) / (len(scores) - mid)
    diff = second_half - first_half
    if diff > 0.5:
        return "improving"
    elif diff < -0.5:
        return "declining"
    return "stable"


def should_nudge(moods: list[dict]) -> bool:
    """Return True if mood has been consistently low (3+ entries below 2.5)."""
    recent = moods[-3:]
    return len(recent) >= 3 and all(m["mood_score"] < 2.5 for m in recent)


def mood_emoji(score: float) -> str:
    if score >= 4.5:
        return "radiant"
    elif score >= 3.5:
        return "warm"
    elif score >= 2.5:
        return "gentle"
    elif score >= 1.5:
        return "tender"
    else:
        return "nurturing"
