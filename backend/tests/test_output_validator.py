# backend/tests/test_output_validator.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from composer.output_validator import OutputValidator
from models.context import (
    TriggerContext, MerchantContext, CategoryContext,
    Identity, Subscription, PerformanceSnapshot, VoiceProfile, PeerStats,
)


def make_merchant(**overrides) -> MerchantContext:
    base = dict(
        merchant_id="m_test_001",
        category_slug="dentists",
        identity=Identity(name="Test Clinic", city="Delhi", locality="Saket",
                           languages=["en"], owner_first_name="Ravi"),
        subscription=Subscription(status="active", plan="growth", days_remaining=100),
        performance=PerformanceSnapshot(window_days=30, views=1000, calls=20, directions=30, ctr=0.02),
        offers=[],
        conversation_history=[],
        signals=[],
    )
    base.update(overrides)
    return MerchantContext(**base)


def make_category(**overrides) -> CategoryContext:
    base = dict(
        slug="dentists",
        voice=VoiceProfile(tone="clinical_peer", register="professional", code_mix="english_primary",
                            vocab_taboo=["guaranteed", "miracle"]),
        peer_stats=PeerStats(avg_rating=4.3, avg_ctr=0.03),
    )
    base.update(overrides)
    return CategoryContext(**base)


def make_trigger(**overrides) -> TriggerContext:
    base = dict(
        id="trg_test_001",
        scope="merchant",
        kind="research_digest",
        source="external",
        merchant_id="m_test_001",
        suppression_key="sup_test_001",
    )
    base.update(overrides)
    return TriggerContext(**base)


class TestOutputValidator:
    def setup_method(self):
        self.validator = OutputValidator()
        self.merchant = make_merchant()
        self.category = make_category()
        self.trigger = make_trigger()

    def test_valid_output_passes(self):
        raw = {
            "body": "Dr. Ravi, your CTR is 2% vs 3% peer median. Want a fix drafted?",
            "cta": "binary_yes_no",
            "send_as": "nexora",
            "template_params": ["Ravi", "ctr_gap", "binary_yes_no"],
            "rationale": "CTR gap signal used with effort-externalization lever.",
        }
        result = self.validator.validate(raw, self.trigger, self.merchant, self.category)
        assert result is not None
        assert result["body"] == raw["body"]
        assert result["cta"] == "binary_yes_no"
        assert result["send_as"] == "nexora"

    def test_empty_body_rejected(self):
        raw = {"body": "", "cta": "open_ended", "send_as": "nexora", "rationale": "x"}
        result = self.validator.validate(raw, self.trigger, self.merchant, self.category)
        assert result is None

    def test_url_in_body_is_stripped(self):
        raw = {
            "body": "Check this out: https://magicpin.com/merchant/xyz for details",
            "cta": "open_ended",
            "send_as": "nexora",
            "rationale": "x",
        }
        result = self.validator.validate(raw, self.trigger, self.merchant, self.category)
        assert result is not None
        assert "http" not in result["body"]

    def test_invalid_cta_defaults_to_open_ended(self):
        raw = {"body": "Some message here", "cta": "not_a_real_cta", "send_as": "nexora", "rationale": "x"}
        result = self.validator.validate(raw, self.trigger, self.merchant, self.category)
        assert result["cta"] == "open_ended"

    def test_send_as_corrected_for_customer_scope(self):
        customer_trigger = make_trigger(scope="customer", kind="recall_due", customer_id="c_001")
        raw = {"body": "Hi, your recall is due.", "cta": "multi_choice_slot", "send_as": "nexora", "rationale": "x"}
        result = self.validator.validate(raw, customer_trigger, self.merchant, self.category)
        assert result["send_as"] == "merchant_on_behalf"

    def test_send_as_corrected_for_merchant_scope(self):
        raw = {"body": "Hi merchant, here is an update.", "cta": "open_ended",
               "send_as": "merchant_on_behalf", "rationale": "x"}
        result = self.validator.validate(raw, self.trigger, self.merchant, self.category)
        assert result["send_as"] == "nexora"

    def test_missing_template_params_backfilled(self):
        raw = {"body": "Your CTR is below peer median.", "cta": "open_ended", "send_as": "nexora", "rationale": "x"}
        result = self.validator.validate(raw, self.trigger, self.merchant, self.category)
        assert len(result["template_params"]) == 3
        assert result["template_params"][0] == "Ravi"

    def test_missing_rationale_backfilled(self):
        raw = {"body": "Message body here.", "cta": "open_ended", "send_as": "nexora", "rationale": ""}
        result = self.validator.validate(raw, self.trigger, self.merchant, self.category)
        assert result["rationale"] != ""
        assert "research_digest" in result["rationale"]

    def test_taboo_word_flagged_but_not_rejected(self):
        raw = {"body": "This treatment is guaranteed to work!", "cta": "open_ended",
               "send_as": "nexora", "rationale": "x"}
        result = self.validator.validate(raw, self.trigger, self.merchant, self.category)
        assert result is not None
        assert "guaranteed" in result["taboo_hits"]

    def test_repeated_body_in_conversation_is_rejected(self):
        raw = {"body": "We already sent this exact message before.", "cta": "open_ended",
               "send_as": "nexora", "rationale": "x"}
        result = self.validator.validate(
            raw, self.trigger, self.merchant, self.category,
            previously_sent_bodies=["We already sent this exact message before."],
        )
        assert result is None

    def test_non_dict_output_rejected(self):
        result = self.validator.validate("not a dict", self.trigger, self.merchant, self.category)
        assert result is None
