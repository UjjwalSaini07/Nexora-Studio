# backend/reply/language_detector.py
"""
LanguageDetector: lightweight heuristic detector for mid-conversation
language switches between English and Hindi/Hinglish (code-mixed).

This is NOT meant to be a full NLP language-ID model — the judge harness
operates on WhatsApp-style short messages where a fast heuristic is more
robust than a heavyweight classifier under the 30s reply budget. It looks
for Devanagari script and a curated list of common romanized Hindi tokens.
"""
import re

DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]")

# Common romanized Hindi/Hinglish tokens seen in WhatsApp business chat.
ROMAN_HINDI_TOKENS = {
    "haan", "nahi", "nahin", "theek", "thik", "bilkul", "kar", "karo", "kare",
    "kya", "kab", "kaise", "kyu", "kyun", "accha", "acha", "bhai", "didi",
    "sahab", "sahib", "ji", "hoga", "hogi", "chalega", "chalegi", "matlab",
    "abhi", "phir", "bahut", "bohot", "shukriya", "dhanyavaad", "namaste",
    "paisa", "paise", "rupiya", "rupaye", "samay", "waqt", "zaroor", "jaroor",
}


class LanguageDetector:
    def detect(self, message: str) -> str:
        """
        Returns one of: "hi" (Devanagari script present), "hi-en" (romanized
        Hindi tokens mixed with English), or "en" (no Hindi signal found).
        """
        if not message:
            return "en"

        if DEVANAGARI_PATTERN.search(message):
            return "hi"

        words = re.findall(r"[a-zA-Z']+", message.lower())
        if not words:
            return "en"

        hindi_hits = sum(1 for w in words if w in ROMAN_HINDI_TOKENS)
        if hindi_hits == 0:
            return "en"
        if hindi_hits >= max(1, len(words) // 2):
            return "hi-en"
        return "hi-en" if hindi_hits >= 1 else "en"

    def has_switched(self, previous_language: str, message: str) -> bool:
        """True if the detected language of `message` differs from the
        language used earlier in the conversation, signalling NEXORA should
        adapt its reply language to match."""
        current = self.detect(message)
        if previous_language == current:
            return False
        # Treat "en" -> "hi-en" and "hi-en" -> "en" both as real switches,
        # but don't flag "hi" vs "hi-en" as a switch (same effective register).
        if {previous_language, current} == {"hi", "hi-en"}:
            return False
        return True
