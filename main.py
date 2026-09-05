import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from supabase import create_client
from act import act_on_payment

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = FastAPI()


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Server is running"}


@app.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    payload = await request.json()

    payment_data = payload["payload"]["payment"]["entity"]

    record = {
        "payment_id": payment_data.get("id"),
        "amount": payment_data.get("amount"),
        "currency": payment_data.get("currency"),
        "failure_reason": payment_data.get("error_reason"),
        "method": payment_data.get("method"),
    }

    # Save the failure first, same as before
    insert_result = supabase.table("failed_payments").insert(record).execute()
    print("Saved failed payment to Supabase:", record)

    # NEW: immediately run the Decide + Act step on this exact payment,
    # instead of waiting for run_batch.py to be run manually later.
    # insert_result.data[0] gives us back the full saved row, including
    # its real id and default status/retry_count, which act_on_payment needs.
    try:
        saved_payment = insert_result.data[0]
        act_on_payment(saved_payment)
        print(f"Acted on payment {saved_payment['id'][:8]}... automatically.")
    except Exception as e:
        # If the AI/Act step fails for any reason, we don't want that to
        # break the webhook response back to Razorpay - the payment is
        # still safely saved either way, just not yet acted on.
        print(f"Act step failed for this payment: {e}")

    return {"status": "received"}