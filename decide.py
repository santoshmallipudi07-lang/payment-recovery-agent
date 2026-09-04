import os
import json
import time
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-3.1-flash-lite")

MAX_ATTEMPTS = 3  # how many times to retry a rate-limited Gemini call before giving up

# This is the "rulebook" we give the AI. Notice it's told EXACTLY which
# 3 actions it's allowed to choose - nothing else is permitted. This is
# what "bounded" means from the brief.
SYSTEM_PROMPT = """You are a payment recovery assistant. Given details about a
failed payment, decide the single best next action.

You may ONLY choose one of these 3 actions:
- "retry": use this if the failure looks temporary (e.g. gateway_technical_error,
  payment_timed_out) and retry_count is less than 2
- "nudge": use this if the customer needs to fix something themselves
  (e.g. insufficient_funds, authentication_failed) and no nudge has been sent yet
- "escalate": use this if retry_count is already 2 or more, or a nudge was
  already sent and still failed, or the reason is unclear

Respond ONLY with valid JSON in this exact format, nothing else:
{"action": "retry" or "nudge" or "escalate", "reasoning": "one short sentence why"}
"""


def decide_action(failed_payment: dict) -> dict:
    """
    Takes one failed payment record (a dict with failure_reason, retry_count, etc.)
    and asks Gemini to decide what to do about it.
    Returns a dict like {"action": "retry", "reasoning": "..."}
    """
    # Build a plain-text summary of this specific payment for the AI to read
    context = f"""
Failed payment details:
- Amount: {failed_payment.get('amount')} paise
- Method: {failed_payment.get('method')}
- Failure reason: {failed_payment.get('failure_reason')}
- Retry count so far: {failed_payment.get('retry_count', 0)}
"""

    full_prompt = SYSTEM_PROMPT + "\n\n" + context

    # Retry a handful of times if the API throws a transient 429/ResourceExhausted
    # (rate limit) so one hiccup doesn't kill the whole batch run.
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = model.generate_content(full_prompt)
            break
        except Exception as e:
            last_error = e
            err_str = str(e)
            if "429" in err_str or "ResourceExhausted" in err_str or "quota" in err_str.lower():
                print(f"   [rate limited, retry {attempt+1}/{MAX_ATTEMPTS}]")
                time.sleep(5 * (attempt + 1))
                if attempt == MAX_ATTEMPTS - 1:
                    # Last chance: fall back to escalate so the row still gets
                    # a decision and the batch keeps going.
                    return {"action": "escalate", "reasoning": f"Rate limited after retries: {err_str[:100]}"}
            else:
                raise e
    else:
        return {"action": "escalate", "reasoning": f"Gemini call failed: {str(last_error)[:100]}"}

    # The AI's reply comes back as text - we need to parse it as JSON.
    # Sometimes models wrap JSON in ```json ... ``` so we clean that up first.
    raw_text = response.text.strip()
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        decision = json.loads(raw_text)
    except json.JSONDecodeError:
        # If the AI didn't return valid JSON, fail safely by escalating
        decision = {"action": "escalate", "reasoning": "Could not parse AI response"}

    return decision


# Quick test - only runs if you execute this file directly
if __name__ == "__main__":
    test_payment = {
        "amount": 10000,
        "method": "card",
        "failure_reason": "insufficient_funds",
        "retry_count": 0,
    }
    result = decide_action(test_payment)
    print("Decision:", result)