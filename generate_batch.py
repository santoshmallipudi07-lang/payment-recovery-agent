import os
import random
import sys
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

print("Connecting to:", SUPABASE_URL)

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_KEY is missing from .env")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

FAILURE_REASONS = [
    "insufficient_funds",
    "payment_timed_out",
    "authentication_failed",
    "gateway_technical_error",
    "payment_failed",
]

METHODS = ["card", "upi", "netbanking"]

NUM_RECORDS = 80

records = []
for i in range(NUM_RECORDS):
    record = {
        "payment_id": f"pay_FAKE{i:04d}",
        "amount": random.choice([5000, 10000, 15000, 25000, 50000]),
        "currency": "INR",
        "failure_reason": random.choice(FAILURE_REASONS),
        "method": random.choice(METHODS),
    }
    records.append(record)

print(f"Attempting to insert {len(records)} records...")

try:
    result = supabase.table("failed_payments").insert(records).execute()
    print(f"SUCCESS: Inserted {len(records)} synthetic failed payments into Supabase.")
except Exception as e:
    print("ERROR while inserting:")
    print(repr(e))