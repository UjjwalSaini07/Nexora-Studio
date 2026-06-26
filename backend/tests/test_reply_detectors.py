# backend/tests/test_reply_detectors.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reply.auto_reply_detector import AutoReplyDetector
from reply.intent_router import IntentRouter
from reply.language_detector import LanguageDetector


class TestAutoReplyDetector:
    def setup_method(self):
        self.detector = AutoReplyDetector()

    def test_detects_canned_english_reply(self):
        assert self.detector.detect("Thank you for contacting us, our team will respond shortly.")

    def test_detects_canned_hindi_reply(self):
        assert self.detector.detect("Aapki jaankari ke liye, bahut-bahut shukriya.")

    def test_does_not_flag_genuine_reply(self):
        assert not self.detector.detect("Yes, let's do it. Send me the draft.")

    def test_empty_message_not_flagged(self):
        assert not self.detector.detect("")


class TestIntentRouter:
    def setup_method(self):
        self.router = IntentRouter()

    def test_detects_explicit_commit_english(self):
        assert self.router.is_explicit_commit("Yes please, go ahead")

    def test_detects_explicit_commit_hindi(self):
        assert self.router.is_explicit_commit("Haan kar do")

    def test_does_not_flag_neutral_message(self):
        assert not self.router.is_explicit_commit("What time does the clinic open?")

    def test_detects_hard_stop(self):
        assert self.router.is_hard_stop("Please stop messaging me")

    def test_detects_hard_stop_hindi(self):
        assert self.router.is_hard_stop("Band karo yeh sab")

    def test_does_not_flag_normal_message_as_hard_stop(self):
        assert not self.router.is_hard_stop("I'll think about it and get back to you")


class TestLanguageDetector:
    def setup_method(self):
        self.detector = LanguageDetector()

    def test_detects_pure_english(self):
        assert self.detector.detect("Sure, please send the draft over") == "en"

    def test_detects_devanagari_as_hi(self):
        assert self.detector.detect("\u0939\u093e\u0902 \u0915\u0930 \u0926\u094b") == "hi"

    def test_detects_romanized_hindi_mix(self):
        result = self.detector.detect("haan bilkul kar do, theek hai")
        assert result == "hi-en"

    def test_empty_message_defaults_to_english(self):
        assert self.detector.detect("") == "en"

    def test_has_switched_detects_change(self):
        assert self.detector.has_switched("en", "haan bilkul karo theek hai") is True

    def test_has_switched_no_change(self):
        assert self.detector.has_switched("en", "Sure, sounds good") is False

    def test_has_switched_hi_to_hi_en_not_flagged(self):
        assert self.detector.has_switched("hi", "haan theek hai") is False
