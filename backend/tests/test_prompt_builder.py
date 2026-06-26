# backend/tests/test_prompt_builder.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from composer.prompt_builder import PromptBuilder
from models.context import (
    CategoryContext, MerchantContext, TriggerContext, CustomerContext,
    Identity, Subscription, PerformanceSnapshot, VoiceProfile, PeerStats,
    DigestItem, MerchantOffer, ConversationTurn, CustomerIdentity, Relationship,
    Preferences, Consent,
)


def make_category():
    return CategoryContext(
        slug="dentists",
        voice=VoiceProfile(
            tone="clinical_peer", register="professional", code_mix="english_primary",
            vocab_allowed=["recall", "caries"], vocab_taboo=["guaranteed", "miracle"],
        ),
        peer_stats=PeerStats(avg_rating=4.3, avg_ctr=0.03),
        digest=[DigestItem(id="dig_001", kind="research", title="Fluoride recall study",
                            source="JIDA Oct 2026 p.14", trial_n=2100, patient_segment="high_risk_adult")],
    )


def make_merchant():
    return MerchantContext(
        merchant_id="m_001",
        category_slug="dentists",
        identity=Identity(name="Test Clinic", city="Delhi", locality="Saket",
                           languages=["en", "hi"], owner_first_name="Meera"),
        subscription=Subscription(status="active", plan="growth", days_remaining=100),
        performance=PerformanceSnapshot(window_days=30, views=1000, calls=20, directions=30, ctr=0.024),
        offers=[MerchantOffer(id="off_1", title="Dental Cleaning @ \u20b9299", status="active")],
        conversation_history=[
            ConversationTurn(**{"ts": "2026-06-01T10:00:00Z", "from": "vera", "body": "Hi there"}),
        ],
        signals=["stale_posts:22d"],
    )


def make_trigger(**overrides):
    base = dict(
        id="trg_001", scope="merchant", kind="research_digest", source="external",
        merchant_id="m_001", payload={"top_item_id": "dig_001"},
        suppression_key="sup_001",
    )
    base.update(overrides)
    return TriggerContext(**base)


class TestPromptBuilder:
    def setup_method(self):
        self.builder = PromptBuilder()

    def test_build_returns_system_and_user(self):
        result = self.builder.build(make_category(), make_merchant(), make_trigger(), None, "2026-06-25T10:00:00Z")
        assert "system" in result and "user" in result
        assert len(result["system"]) > 0
        assert len(result["user"]) > 0

    def test_research_digest_addendum_included(self):
        result = self.builder.build(make_category(), make_merchant(), make_trigger(), None, "2026-06-25T10:00:00Z")
        assert "research_digest" in result["system"]
        assert "FRAME AS" in result["system"]

    def test_digest_item_extracted_into_prompt(self):
        result = self.builder.build(make_category(), make_merchant(), make_trigger(), None, "2026-06-25T10:00:00Z")
        assert "Fluoride recall study" in result["user"]
        assert "JIDA Oct 2026 p.14" in result["user"]
        assert "2100" in result["user"]

    def test_taboo_words_listed_in_prompt(self):
        result = self.builder.build(make_category(), make_merchant(), make_trigger(), None, "2026-06-25T10:00:00Z")
        assert "guaranteed" in result["user"]
        assert "miracle" in result["user"]

    def test_hindi_language_instruction_included(self):
        result = self.builder.build(make_category(), make_merchant(), make_trigger(), None, "2026-06-25T10:00:00Z")
        assert "code-mix" in result["user"].lower()

    def test_english_only_merchant_gets_english_instruction(self):
        merchant = make_merchant()
        merchant.identity.languages = ["en"]
        result = self.builder.build(make_category(), merchant, make_trigger(), None, "2026-06-25T10:00:00Z")
        assert "Use English" in result["user"]

    def test_conversation_history_included_for_anti_repetition(self):
        result = self.builder.build(make_category(), make_merchant(), make_trigger(), None, "2026-06-25T10:00:00Z")
        assert "Hi there" in result["user"]
        assert "DO NOT REPEAT" in result["user"]

    def test_unknown_trigger_kind_uses_default_addendum(self):
        trigger = make_trigger(kind="some_unknown_kind", payload={})
        result = self.builder.build(make_category(), make_merchant(), trigger, None, "2026-06-25T10:00:00Z")
        assert "some_unknown_kind" in result["system"]

    def test_customer_context_included_when_present(self):
        customer = CustomerContext(
            customer_id="c_001", merchant_id="m_001",
            identity=CustomerIdentity(name="Rakesh Kumar", language_pref="hi-en"),
            relationship=Relationship(visits_total=6, services_received=["Dental Cleaning"]),
            state="active",
            preferences=Preferences(preferred_slots="evening"),
            consent=Consent(scope=["recall_reminders"]),
        )
        trigger = make_trigger(scope="customer", kind="recall_due", customer_id="c_001", payload={})
        result = self.builder.build(make_category(), make_merchant(), trigger, customer, "2026-06-25T10:00:00Z")
        assert "Rakesh Kumar" in result["user"]
        assert "CUSTOMER CONTEXT" in result["user"]

    def test_no_customer_section_when_merchant_scoped(self):
        result = self.builder.build(make_category(), make_merchant(), make_trigger(), None, "2026-06-25T10:00:00Z")
        assert "CUSTOMER CONTEXT" not in result["user"]
