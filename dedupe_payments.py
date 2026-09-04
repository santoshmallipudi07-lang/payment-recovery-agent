import os
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

if __name__ == "__main__":
    all_payments = supabase.table("failed_payments").select("*").execute().data
    print(f"Total rows before cleanup: {len(all_payments)}")

    # Group rows by their business key (payment_id). Real webhook payments
    # will have real Razorpay ids (pay_xxxxxxx...), synthetic ones look
    # like pay_FAKE0000, pay_FAKE0001, etc. Either way, duplicates share
    # the exact same payment_id text.
    groups = defaultdict(list)
    for p in all_payments:
        groups[p["payment_id"]].append(p)

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"Found {len(duplicate_groups)} payment_ids with duplicates.")

    ids_to_delete = []
    for payment_id, rows in duplicate_groups.items():
        # Prefer to KEEP a row that already has activity (status != "open"),
        # so we don't throw away real progress from the earlier partial batch run.
        # Among ties, keep the earliest created row.
        rows_sorted = sorted(
            rows,
            key=lambda r: (r.get("status") == "open", r.get("created_at", "")),
        )
        keep = rows_sorted[0]
        remove = rows_sorted[1:]
        ids_to_delete.extend(r["id"] for r in remove)

    print(f"Will delete {len(ids_to_delete)} duplicate rows, keeping {len(duplicate_groups)}.")

    # Delete in batches to avoid overly long queries
    BATCH_SIZE = 50
    for i in range(0, len(ids_to_delete), BATCH_SIZE):
        chunk = ids_to_delete[i:i + BATCH_SIZE]
        supabase.table("failed_payments").delete().in_("id", chunk).execute()
        print(f"  Deleted {min(i + BATCH_SIZE, len(ids_to_delete))}/{len(ids_to_delete)}")

    remaining = supabase.table("failed_payments").select("id").execute().data
    print(f"\nDone. Total rows after cleanup: {len(remaining)}")
