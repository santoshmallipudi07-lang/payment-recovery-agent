# AI Revenue Recovery Agent
### Razorpay Buildathon — Track 03: AI Revenue Recovery

An autonomous agent that detects failed payments, decides the right recovery
action, executes it within hard-coded safety limits, and logs every decision
for a full audit trail.

## The Problem

When a customer's payment fails, that revenue is usually just lost — nobody
follows up, and the sale is gone. This agent catches every failed payment in
real time and automatically tries to win it back, without needing a human to
watch and react manually.

## How It Works

The agent runs a 5-step loop on every failed payment:

1. **Trigger** — Razorpay sends a `payment.failed` webhook the moment a
   payment fails (real-time, via Razorpay's test-mode APIs).
2. **Understand** — The failure is saved to a database with full context:
   amount, method, and failure reason.
3. **Decide** — The payment's details are sent to an AI model (Gemini), which
   picks exactly ONE of three allowed actions: `retry`, `nudge`, or
   `escalate` — with a one-sentence reason for its choice.
4. **Act** — The chosen action is carried out, and the outcome is logged.
5. **Measure** — Results are aggregated into a live dashboard showing total
   money recovered, recovery rate, and every decision's audit trail.

### Bounded & Gated (the safety layer)

The AI never has unrestricted control over money actions. Two hard-coded
rules, enforced in code (not left to the AI's judgment), decide whether the
AI is even allowed to act further on a payment:

- **Max attempts: 1.** Every payment gets exactly one attempt (a retry OR a
  nudge). If that attempt doesn't resolve the payment, it's automatically
  escalated to a human — it is never retried or nudged indefinitely.
- **Compliant escalation.** Once a payment is escalated, the agent takes no
  further automated action on it. It sits in a "needs human review" queue.

This means the AI only ever decides *which* of three pre-approved actions
fits a given failure — it can never invent a new action, retry endlessly, or
act on an already-escalated payment.

## Real Results (from a live batch of 91 failed payments)

| Metric | Value |
|---|---|
| Total payments processed | 91 |
| Total amount at risk | ₹44,600.00 |
| Total amount recovered | ₹4,850.00 |
| Recovery rate | 27.5% |
| Recovered | 25 |
| Escalated to human | 66 |
| Still open | 0 |

Every payment reached a final, clean state — none were left stuck in limbo.

## Honest Disclosures

We believe an honest system is more valuable than an impressive-looking one.
Two things are deliberately simulated, and here's exactly why:

- **Retry success is simulated at a 60% success rate.** Razorpay's test mode
  cannot be forced to return a real successful payment on retry, so we
  simulate this probability rather than faking a 100% success rate. This is
  the same limitation any developer building against Razorpay's sandbox
  would hit — the decision logic and stopping rules around it are 100% real.
- **Nudge messages are logged, not actually sent via WhatsApp/SMS.** The
  agent decides to send a nudge and records that decision and its content,
  but does not integrate with a live messaging provider in this build.

Everything else — the webhook, the database writes, the AI decision-making,
the stopping rules, and the audit log — is fully real and live.

## Tech Stack

- **Backend:** Python, FastAPI, deployed on Render
- **Database:** Supabase (Postgres)
- **AI:** Google Gemini API (`gemini-3.1-flash-lite`)
- **Frontend:** React + TypeScript, deployed on Vercel, with a live Supabase
  realtime subscription so new decisions appear instantly, no refresh needed
- **Payments:** Razorpay test-mode APIs + webhooks

## Architecture

```
Razorpay (test mode)
      │  payment.failed webhook
      ▼
FastAPI backend (Render)
      │  saves to failed_payments
      ▼
Gemini AI decides: retry / nudge / escalate
      │
      ▼
Stopping rules enforced in code
      │  action executed, logged to action_log
      ▼
Supabase (Postgres)
      │  realtime subscription
      ▼
React dashboard (Vercel) — live audit trail & metrics
```

## Running It

1. Clone the repo and `pip install -r requirements.txt`
2. Add `.env` with: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `SUPABASE_URL`,
   `SUPABASE_SERVICE_KEY`, `GEMINI_API_KEY`
3. Run the SQL in `schema.sql` (or the SQL Editor script) to create the
   `failed_payments` and `action_log` tables in Supabase
4. `uvicorn main:app --reload` to start the webhook server
5. Register the webhook URL (+ `/webhook/razorpay`) in Razorpay's dashboard
   for the `payment.failed` event
6. Optional: `python generate_batch.py` to seed synthetic test data, then
   `python run_batch.py` to run the agent across the full batch
7. The dashboard (`recovery-dashboard/`) reads live from Supabase — no
   backend connection needed for viewing

## What We'd Add Next

- Real WhatsApp/SMS delivery for nudge messages (Twilio integration)
- A genuine retry via Razorpay's mandate/recurring APIs instead of a
  simulated outcome
- Configurable stopping-rule thresholds per merchant
