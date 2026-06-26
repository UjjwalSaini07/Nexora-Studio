# backend/reply/auto_reply_detector.py
from config import AUTO_REPLY_PATTERNS


class AutoReplyDetector:
    def detect(self, message: str) -> bool:
        msg_lower = (message or "").lower()
        return any(pattern in msg_lower for pattern in AUTO_REPLY_PATTERNS)
