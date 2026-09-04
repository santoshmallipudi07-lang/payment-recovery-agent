import os
import time
from dotenv import load_dotenv
from supabase import create_client
from act import act_on_payment

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

if __name__ == "__main__":
    # Grab every payment that's still "open" (not already recovered/escalated)
    result = supabase.table("failed_payments").select("*").eq("status", "open").execute()
    payments = result.data

    print(f"Found {len(payments)} open payments. Running Act step on each...")

    for i, payment in enumerate(payments, start=1):
        try:
            act_on_payment(payment)
        except Exception as e:
            print(f"Payment {payment['id'][:8]}... FAILED with error: {e}")
        time.sleep(1)  # avoid hammering Gemini's free-tier quota
        if i % 10 == 0:
            print(f"...processed {i}/{len(payments)}")

    print("\nBatch run complete. Fetching summary...")

    # Pull final numbers straight from Supabase
    all_payments = supabase.table("failed_payments").select("*").execute().data
    total_at_risk = sum(p["amount"] for p in all_payments) / 100  # paise -> rupees
    recovered = [p for p in all_payments if p["status"] == "recovered"]