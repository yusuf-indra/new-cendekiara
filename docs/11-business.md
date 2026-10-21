# 11 — Business model (plan, built in Phase 10)

- **Free** tier with limited quota (free packages, a daily number of Study /
  Practice questions).
- **Credits** (pay per use: AI-scored Writing/Speaking, premium packages),
  **bundles**, and **prepaid subscriptions** (1/3/12 months, renewed
  manually with reminders). All prices and quotas are set by admins and
  stored in Firestore, never in code.
- Payments on web: **Midtrans** behind `services/payments/` (interface so
  Stripe/Xendit can be added). Android: Google Play Billing.
- **Voucher codes** (sold on TikTok/marketplaces/resellers),
  **promo and referral codes** for creator affiliates.
- Every channel ends in one **ledger** entry (`ledger/`) → the user's
  credits / plan. Balances are derived from the ledger; webhooks are
  verified and idempotent.
- **Turnstile** on sign-up against free-quota abuse.
- Paid features (e.g. notes mode limits) are switched by plan checks inside
  commands (`core/entitlements.py`), never in the frontend alone.
