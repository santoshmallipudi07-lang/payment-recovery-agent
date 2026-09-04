import os
from dotenv import load_dotenv
from supabase import create_client
from decide import decide_action

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

MAX_RETRIES = 2
MAX_NUDGES = 1


def act_on_payment(payment):
    """
    Takes one failed_payment row, asks Gemini what to do,
    enforces stopping rules, does the action, logs everything.
    """
    payment_id = payment["id"]
    retry_count = payment.get("retry_count", 0) or 0
    status = payment.get("status", "open")

    # Stopping rule check FIRST, before even asking the AI.
    # This is the "bounded" part - the code decides if the AI is even
    # allowed to act, the AI only decides WHICH action within that.
    if status == "escalated":
        return  # already escalated, do nothing more

    if retry_count >= MAX_RETRIES:
        outcome = "escalated_max_retries_reached"
        action_taken = "escalate"
        reasoning = f"Stopping rule: {retry_count} retries already attempted, limit is {MAX_RETRIES}."
        supabase.table("failed_payments").update({"status": "escalated"}).eq("id", payment_id).execute()
        supabase.table("action_log").insert({
            "failed_payment_id": payment_id,
            "action_taken": action_taken,
            "reasoning": reasoning,
            "outcome": outcome,
        }).execute()
        return

    # Ask Gemini what to do
    decision = decide_action(payment)
    action = decision.get("action", "escalate")
    reasoning = decision.get("reasoning", "No reasoning provided.")

    if action == "retry":
        # Simulate a retry attempt. In test mode we can't force a real
        # success, so we simulate a ~60% recovery chance - this is
        # honest and documented, not hidden, in the README.
        import random
        success = random.random() < 0.6
        new_retry_count = retry_count + 1
        if success:
            outcome = "recovered"
            supabase.table("failed_payments").update({
                "status": "recovered",
                "retry_count": new_retry_count,
            }).eq("id", payment_id).execute()
        else:
            outcome = "retry_failed"
            supabase.table("failed_payments").update({
                "retry_count": new_retry_count,
            }).eq("id", payment_id).execute()

    elif action == "nudge":
        # Simulate sending a message to the customer (logged, not
        # actually sent via WhatsApp - documented scope decision).
        outcome = "nudge_sent"
        supabase.table("failed_payments").update({
            "status": "open",
        }).eq("id", payment_id).execute()

    else:  # escalate
        outcome = "escalated_by_agent"
        supabase.table("failed_payments").update({
            "status": "escalated",
        }).eq("id", payment_id).execute()

    supabase.table("action_log").insert({
        "failed_payment_id": payment_id,
        "action_taken": action,
        "reasoning": reasoning,
        "outcome": outcome,
    }).execute()

    print(f"Payment {payment_id[:8]}... -> {action} -> {outcome}")


if __name__ == "__main__":
    # Quick single-record test before running the full batch
    result = supabase.table("failed_payments").select("*").eq("status", "open").limit(1).execute()
    if result.data:
        act_on_payment(result.data[0])
        print("Single test complete. Check Supabase action_log table.")
    else:
        print("No open payments found to test with.")
