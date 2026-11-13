# NextTo — hyperlocal deals marketplace

React (Vite, TypeScript) front end + FastAPI + SQLite back end. Consumer and merchant screens are mobile-first (open the site on a phone in Chrome and it fills the screen; on a desktop it shows as a phone-width column). The admin dashboard is a wide responsive layout.

## Run
    run.bat            # builds the web app, starts everything on http://localhost:8000
Dev mode: `cd backend && python -m uvicorn app.main:app --reload` and `cd frontend && npm run dev` (http://localhost:5173, proxies /api).
On a phone (same Wi-Fi): open `http://<your-PC-LAN-IP>:8000` in Chrome (allow Python through the Windows firewall on first run).

## Demo accounts (seeded automatically on first start; delete `backend/nextto.db` to reset)
| Role | Email | Password |
|---|---|---|
| Consumer | kartik@demo.com | demo123 |
| Consumer | priya@demo.com | demo123 |
| Merchant (cafe, approved) | cafe@demo.com | demo123 |
| Merchant (salon, approved) | salon@demo.com | demo123 |
| Merchant (pending approval) | new@demo.com | demo123 |
| Admin | admin@nextto.dev | admin123 |

## Tests
    cd backend && python -m pytest tests -q          # 74 tests
    python scripts/e2e_demo.py                        # 21-step journey against the running server

## Architecture (see context.md and docs/)
- `backend/app/db.py` schema + `tx()` (BEGIN IMMEDIATE) — every money/stock/voucher change is one atomic transaction.
- `backend/app/services.py` orders, signed webhook, expiry, reconciliation, redemption, refunds, bookings.
- `backend/app/providers.py` `PaymentProvider` (Simulated HMAC provider, Razorpay test adapter) and `RiskScorer` (Phase-2 fraud plug-in).
- `backend/app/ranking.py` explainable deal scoring (0.50 distance, 0.25 category, 0.15 recency, 0.10 urgency).
- Roles live in a server-only column and travel in the signed JWT as `app_role`.
- Demo payment: "Pay with UPI (simulated)" builds an HMAC-signed callback and sends it through the real webhook path; set `NEXTTO_PROVIDER=razorpay` plus keys for Razorpay test mode.

## Hosting (demo)
- **Backend:** Render (free) from `render.yaml` — create a Blueprint from this repo. Data is seeded on start and resets when the service restarts or redeploys (SQLite on an ephemeral disk); the free tier sleeps after idle, so the first request can take ~30-50 s.
- **Frontend:** Vercel, project root `frontend/`. `frontend/vercel.json` proxies `/api/*` to the Render URL — edit the hostname there if your Render service is not named `nextto-api`.
- Production would use PostgreSQL (Phase 2) instead of SQLite.
