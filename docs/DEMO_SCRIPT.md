# NextTo - demo script (about 8 minutes; short version below)

## 0. Before you start (do this 10 minutes early)

| What | How |
|---|---|
| **Pick where to demo** | **Laptop (most reliable):** run `run.bat`, open `http://localhost:8000`. **Hosted:** `https://nextto.vercel.app` (the free Render server sleeps when idle, so open it a few minutes early; the first load can take 30-50 s). |
| **Fresh data** | Local: stop the server, delete `backend/nextto.db*`, start again. Hosted: the demo data resets whenever Render restarts. Use fresh data so the queues below are full. |
| **Phone (same Wi-Fi)** | Open `http://<your-PC-IP>:8000` in Chrome (find the IP with `ipconfig`; it was 192.168.0.3 earlier). Allow Python through the Windows firewall if asked. |
| **Android app** | On the phone open `https://nextto.vercel.app/NextTo.apk` (or scan the QR code in the report/slide 12), allow "install from this source", install, open. It shows the **shopper side only**. |
| **Three windows** | Shopper at `/` (phone-width), Merchant at `/merchant` (desktop), Admin at `/admin` (desktop, keep this link private). Each has its own sign-in page with one-tap demo buttons, accepts **only its own role**, and keeps its **own session**, so all three can stay signed in side by side in one browser. |

### Demo accounts (password `demo123`; admin `admin123`)

| Portal | Sign-in page | One-tap buttons / accounts |
|---|---|---|
| Shopper | `/login` | **Kartik** (kartik@demo.com), **Leah** (leah@demo.com) |
| Merchant | `/merchant/login` | **Demo cafe** (cafe@demo.com), **Demo salon** (salon@demo.com), **Pending business** (new@demo.com) |
| Admin | `/admin/login` | **Demo admin** (admin@nextto.dev) |

### What the fresh data already contains (so you know what to expect)
- Admin queues: **1 merchant pending** (Spice Route), **1 deal pending** (Weekend Brunch for Two), **1 refund open** (Leah, gym membership).
- Kartik: a redeemed coffee voucher (already reviewed), an **active salon voucher with a booked appointment**, and 12 reward points.
- Leah: a redeemed cake voucher, an active puff voucher, a gym voucher with a refund request.
- Payouts: none yet; two redeemed vouchers are waiting to be settled.

## 1. The 12-step demo

| # | Window | Do this | Say / show |
|---|---|---|---|
| 1 | Shopper | Tap **Kartik**. On Home allow or deny location. | Deals are ranked by distance, category, recency and urgency. If location is refused, an **area picker** appears. Show the category chips, **Within 5 km**, the **Map** toggle and an **Ending Soon** badge. |
| 2 | Merchant | `/merchant/login` > **Pending business**. | A new business is **"Under review"**. The merchant role is granted only after an admin approves. |
| 3 | Admin | `/admin/login` > **Demo admin** > **Merchants** > approve **Spice Route**. Back in the merchant window press **Check status**. | The decision is audited. The token refreshes and the merchant tools (Deals, Redeem, Bookings) unlock. |
| 4 | Merchant | Sign out, then **Demo cafe** > **Deals** > **+ New deal**. Fill the form and **Save & submit**. | The deal is **pending** and invisible to shoppers. A merchant cannot make a deal live. |
| 5 | Admin | **Deals** > approve it. | Only the admin can set a deal active. Editing a live deal sends it back for review. |
| 6 | Shopper | Open the new deal > **Buy now**. Optionally spend reward points. Press **Pay with UPI**, then **Pay with UPI (simulated)**. | Stock is **reserved for 10 minutes**. The order becomes paid **only through a signed webhook**. The idempotency key means a double tap cannot create two orders. |
| 7 | Shopper | **Wallet** > open the voucher. Then open the deal and tap the shop name. | A **signed QR** plus the code. It works once. The **shop profile** shows photo, hours, rating, live deals, map and verified reviews. |
| 8 | Merchant | **Redeem voucher** > type the code (or **Scan QR with camera**) > **Check voucher** > **Redeem**. Then scan the same code again. | The shopper's voucher flips to **Redeemed** by itself. The second scan is refused (**already redeemed**). Points are awarded at redemption. |
| 9 | Shopper | Open the redeemed voucher and leave a **review and tip**; pay the tip. | One review per redeemed voucher; a tip is just another payment. |
| 10 | Admin | **Refunds** > decide Leah's gym request: approve, or reject with a reason. | The voucher was frozen as `refund_pending`, so it could not be used meanwhile. |
| 11 | Admin | **Payouts** > **Run settlement** > **Release**. | 10% platform fee; refunded vouchers are never paid out; tips pass through. |
| 12 | Admin | **Audit log**. | Every financial or admin change is recorded with before and after values. |

## 2. Optional: show it is robust (pick one or two)
- **Lost callback:** at checkout open **Demo controls** > **callback lost**. The order stays pending. Then Admin > **Overview** > **Reconcile payments now**: the voucher appears.
- **Wrong amount:** Demo controls > **wrong amount**. No voucher is issued and the payment is refunded automatically.
- **Payment failed:** Demo controls > **failed**. The reserved stock is released.
- **Expiry:** an unpaid order older than 10 minutes expires and the stock comes back (Admin > Overview > **Run expiry**).
- **Dark mode / splash:** tap the sun/moon button in the top bar to switch theme; close and reopen the Android app to show the splash screen.
- **Role separation:** try Kartik's login on `/merchant/login`. The server refuses it.

## 3. Short version (3 minutes)
1. Shopper: discover, open a deal, buy it with the simulated UPI button (steps 1, 6).
2. Shopper: show the QR in the wallet (step 7).
3. Merchant: redeem it, then scan again to show the refusal (step 8).
4. Admin: open the audit log (step 12).

Say in one breath: *"Money, stock and vouchers stay correct even if requests repeat or two people act at the same instant."*

## 4. If something goes wrong
| Problem | Fix |
|---|---|
| Home shows "Finding your location..." | It falls back to the area picker after about 6 seconds. Just wait or pick an area. |
| Hosted site is slow on the first click | Render was asleep. Wait up to 50 s once. |
| Phone cannot open the PC address | Same Wi-Fi? Check the IP with `ipconfig`; allow Python in the Windows firewall. |
| Queues are empty or data looks used | Reset the data (section 0) before you start. |
| Camera scanning does not start | Use "enter code manually"; it works the same. |
| Signed in but see the wrong screen | Each portal has its own session; open the right address (`/`, `/merchant`, `/admin`). |

## 5. Likely viva questions (short answers; fuller ones are in `Technical_Terms_Explained.docx`)
- **Why SQLite and FastAPI instead of Supabase?** One runnable stack that could be built and demonstrated quickly. Atomicity is kept with `BEGIN IMMEDIATE` transactions; the Supabase / PostgreSQL design is the Phase-2 migration.
- **How is double redemption prevented?** One conditional `UPDATE ... WHERE status='active' AND valid_until>now AND merchant_id=?`. Five simultaneous scans in the test: exactly one succeeds.
- **How do you trust a payment?** Only the HMAC-verified webhook can mark an order paid; the event ID is de-duplicated and the amount is checked. The client can never set it.
- **What is not built yet?** Live Razorpay/Cashfree testing, native Expo apps, PostgreSQL, push and email delivery, an ML fraud model, CI and a pilot.
