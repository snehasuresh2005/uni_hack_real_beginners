import time
from datetime import datetime

PROVIDER_STATUS = {
    "gemini": {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""},
    "groq": {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""},
    "openrouter": {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""}
}

def mark_provider_daily_exhausted(provider, reason, duration_hours=24):
    reset_timestamp = time.time() + (duration_hours * 3600)
    reset_iso = datetime.fromtimestamp(reset_timestamp).isoformat()
    PROVIDER_STATUS[provider] = {
        "is_disabled": True,
        "cooldown_until": reset_timestamp,
        "disabled_reason": f"{reason} (Cooldown until {reset_iso})"
    }
    print(f"[LLM Quota Tracker] Provider '{provider}' marked DAILY EXHAUSTED until {reset_iso}. Reason: {reason}")

# Test daily quota detection
test_gemini_error = 'HTTP Error 429: {"error": {"details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}'

if "PerDay" in test_gemini_error or "QuotaFailure" in test_gemini_error:
    mark_provider_daily_exhausted("gemini", "Daily Free Tier Quota Exhausted (20 requests/day)")

print("Provider Status after failure:", PROVIDER_STATUS)
