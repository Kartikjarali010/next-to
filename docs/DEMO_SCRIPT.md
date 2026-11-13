# NextTo — demo script (about 8 minutes)

**Before you start:** run `run.bat` (or the server is already up). Open `http://localhost:8000` on the laptop. On your phone (same Wi-Fi), open `http://192.168.0.3:8000` in Chrome and allow Python through the Windows firewall if asked. To reset the data, stop the server, delete `backend/nextto.db*` and start it again.

Use three browser windows or profiles: **Shopper** (phone-width), **Merchant** (phone-width), **Admin** (wide). The login page has one-tap demo chips.

| # | Who | Do this | Say / show |
|---|---|---|---|
| 1 | Shopper | Open the app, allow or deny location. | Deals ranked by distance, category, recency and urgency. If location is denied, an area picker appears. Toggle **Map**. |
| 2 | Merchant (`new@demo.com`) | Sign in. | A new business is "under review". The merchant role is not granted until an admin approves. |
| 3 | Admin | **Merchants** > approve "Spice Route". | The decision is audited. Back in the merchant window, **Check status** > the merchant tools unlock. |
| 4 | Merchant (`cafe@demo.com`) | **Deals** > **+ New deal** > Save & submit. | The deal is pending and invisible to shoppers. |
| 5 | Admin | **Deals** > approve it. | Only an admin can set a deal active. Editing a live deal sends it back for review. |
| 6 | Shopper | Open the deal > **Buy now** > **Pay with UPI (simulated)**. | Stock is reserved for 10 minutes. The payment is accepted only through a **signed webhook**. The idempotency key prevents duplicate orders. |
| 7 | Shopper | **Wallet** > open the voucher. | Signed QR plus code. |
| 8 | Merchant | **Redeem** > scan the QR (or type the code) > **Redeem**. | The shopper's voucher screen flips to **Redeemed** by itself. Scan again to show "already redeemed". |
| 9 | Shopper | Leave a review with a tip, and pay the tip. | Points were credited at redemption. |
| 10 | Admin | **Refunds**: approve or reject the pending request for Priya. | The voucher was frozen in `refund_pending`, so it could not be redeemed meanwhile. |
| 11 | Admin | **Payouts** > Run settlement > Release. | 10% platform fee; refunded vouchers are never paid out. |
| 12 | Admin | **Audit log**. | Every state change is recorded with before and after values. |

## Failure scenarios (show these if asked about robustness)
- Checkout > **Demo controls** > **callback lost**. Then Admin **Overview** > **Reconcile payments now**: the voucher appears.
- Checkout > **Demo controls** > **wrong amount**: no voucher, the payment is auto-refunded.
- Let a pending order run past 10 minutes: it expires and the stock comes back.

## Likely viva questions
- **Why SQLite and FastAPI instead of Supabase?** Chosen for build speed and zero setup. Atomicity is preserved with `BEGIN IMMEDIATE` transactions. The design doc's Supabase/Postgres stack is the Phase-2 migration.
- **How is double redemption prevented?** One conditional `UPDATE ... WHERE status='active' AND valid_until>now AND merchant_id=?`. The test spawns 5 simultaneous scans and exactly 1 succeeds.
- **How do you trust a payment?** Only the HMAC-verified webhook. The client never marks anything paid. The event id is deduplicated and the amount is checked.
- **What is not built yet?** Native Expo apps, live Razorpay or Cashfree keys, push and email delivery, phone OTP, an ML fraud model, and CI.
