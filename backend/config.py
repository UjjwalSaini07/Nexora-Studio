import os
from dotenv import load_dotenv

load_dotenv()

def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_CHAT_ENDPOINT = f"{GROQ_BASE_URL}/chat/completions"

# Default model: fast + strong instruction following, comfortably fits the
# 30s end-to-end budget required by /v1/reply and /v1/tick.
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "llama-3.1-8b-instant")

LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "600"))   # Tight — WhatsApp messages, not essays
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))  # Deterministic: same input -> same output
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "22"))  # Leaves buffer under the 30s SLA

# ── Datastores ───────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "nexora_bot")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ── Team / submission metadata (exposed via /v1/metadata) ─────────────────
TEAM_NAME = os.getenv("TEAM_NAME", "NEXORA Engine")
TEAM_MEMBERS = [m.strip() for m in os.getenv("TEAM_MEMBERS", "Ujjwal Saini").split(",") if m.strip()]
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "ujjwalsaini0007@gmail.com")
BOT_VERSION = os.getenv("BOT_VERSION", "1.0.0")
SUBMITTED_AT = os.getenv("SUBMITTED_AT", "2026-04-26T08:00:00Z")

# ── Operational limits ──────────────────────────────────────────────────────
TICK_MAX_ACTIONS = int(os.getenv("TICK_MAX_ACTIONS", "20"))
CONTEXT_PAYLOAD_SIZE_CAP_KB = int(os.getenv("CONTEXT_PAYLOAD_SIZE_CAP_KB", "500"))
REPLY_TIMEOUT_SECONDS = float(os.getenv("REPLY_TIMEOUT_SECONDS", "28"))
TICK_TIMEOUT_SECONDS = float(os.getenv("TICK_TIMEOUT_SECONDS", "25"))

# ── Auth ─────────────────────────────────────────────────────────────────────
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")
ENABLE_AUTH = _get_bool("ENABLE_AUTH", False)

# ── Rate limiting ────────────────────────────────────────────────────────────
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "1200"))

# ── Demo Mode / Ignore Suppression ───────────────────────────────────────────
DEMO_MODE = _get_bool("DEMO_MODE", True) or _get_bool("IGNORE_SUPPRESSION", True)  # For backwards compatibility with old env var name

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Auto-reply detection patterns (WhatsApp Business canned responses)
AUTO_REPLY_PATTERNS = [
    "thank you for contacting",
    "aapki jaankari ke liye",
    "our team will respond",
    "automated assistant",
    "main ek automated",
    "we will get back to you",
    "bahut-bahut shukriya",
    "this is an automated message",
    "currently unavailable",
    "business hours",
    "dhanyavaad sampark karne ke liye",
]
