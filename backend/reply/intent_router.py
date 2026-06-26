# backend/reply/intent_router.py
COMMIT_SIGNALS = [
    "ok let's do it", "ok lets do it", "yes let's go", "yes go ahead",
    "yes please", "haan", "haan karo", "kar do", "go", "yes, do it",
    "sounds good, let's start", "theek hai", "bilkul", "chalega",
    "confirm", "let's start", "start kar do",
]
HARD_STOP_SIGNALS = [
    "stop messaging", "not interested", "band karo", "mat karo",
    "stop", "remove me", "unsubscribe", "don't message",
    "go away", "annoying", "bakwaas",
]


class IntentRouter:
    def is_explicit_commit(self, message: str) -> bool:
        msg = (message or "").lower().strip()
        return any(s in msg for s in COMMIT_SIGNALS)

    def is_hard_stop(self, message: str) -> bool:
        msg = (message or "").lower().strip()
        return any(s in msg for s in HARD_STOP_SIGNALS)
