import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from supabase import create_client

# This reads your .env file and makes RAZORPAY_KEY_ID, SUPABASE_URL, etc.
# available to this code via os.environ.get(...)
load_dotenv()

# Read your Supabase credentials from .env
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# Create a connected client we can use to talk to your Supabase database
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = FastAPI()


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Server is running"}


@app.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    payload = await request.json()

    # Reach into the nested JSON Razorpay sends us to get just the
    # actual payment details (id, amount, failure reason, etc.)
    payment_data = payload["payload"]["payment"]["entity"]

    # Build a clean record matching our failed_payments table columns
    record = {
        "payment_id": payment_data.get("id"),
        "amount": payment_data.get("amount"),
        "currency": payment_data.get("currency"),
        "failure_reason": payment_data.get("error_reason"),
        "method": payment_data.get("method"),
    }

    # Actually save this record into the failed_payments table in Supabase
    supabase.table("failed_payments").insert(record).execute()

    print("Saved failed payment to Supabase:", record)

    return {"status": "received"}