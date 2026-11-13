# NextTo — Project Context

_Consolidated from the files in Downloads (13 Nov 2026). Source of truth for aligning before we build._

## 1. What it is
**NextTo: A Hyperlocal Deals Marketplace for Local Businesses and Consumers.**
Merchants publish time-bound discounted offers; nearby consumers discover them, pay by UPI, get a single-use QR voucher, and redeem in person. Services can be booked by appointment. Admins approve merchants/deals/refunds and see an audit trail.

- Institution: REVA University (School of CSE), Bengaluru. Track: "Other", Center for Cyber Security & Digital Trust. Faculty guide: Dr Chaithra M H.
- Team: Kartik Jarali (R23EF107); the weekly reports also name Leah C. The KSCST proposal lists only Kartik, with the other team slots blank.
- Also submitted to **KSCST SPP 2026-27** (proposal, 5 months, budget Rs 10,000; patent search promised in Month 1; pilot of >=5 merchants and 50 consumers near campus).
- Course deliverables are weekly RIO tasks (Week 1-8 reports). The next checkpoint is after Week 8, which was reported at about 30% complete.

## 2. Roles and apps
| Actor | Surface |
|---|---|
| Consumer | Expo (React Native) mobile app + Vite/React website |
| Merchant | Expo mobile app |
| Admin | Vite/React dashboard |
| External | Razorpay or Cashfree (UPI), push/email, maps/geocoding |

## 3. Fixed tech stack (from the project brief)
- Mobile: React Native + Expo (TypeScript). Web/Admin: Vite + React (TypeScript).
- Backend: Supabase (Auth, PostgREST+RLS, Edge Functions, Realtime, Storage) on PostgreSQL + PostGIS.
- Payments: UPI via Razorpay or Cashfree (undecided; test mode). CI/CD: GitHub Actions; EAS for mobile builds.
- Shared generated TypeScript types package and one API contract across all clients.
- INR only, single region, India-first.

## 4. Architecture rules (the design's key decisions)
1. Clients never hold secrets and never write payment/voucher tables. Low-risk own-data reads/writes use PostgREST + RLS. Anything touching money, stock, vouchers, approvals or third parties goes through an Edge Function.
2. Every atomic operation (reserve stock, confirm payment, redeem voucher, decide refund) is **one PostgreSQL function** called via `rpc()`.
3. Role lives in a server-only `user_roles` table and is injected into the JWT as the `app_role` claim by a Supabase access-token hook. It is never read from a client-editable field.
4. The signed payment webhook is the only proof of payment (HMAC over the raw body, event-id dedup, amount check). `payment-webhook` is deployed without JWT verification.
5. Orders are idempotent (`unique(consumer_id, idempotency_key)`; `Idempotency-Key` header).
6. Redemption is a single conditional UPDATE (active, not expired, scanning merchant owns the deal).
7. Ranking is simple and explainable: `score = 0.50*distance + 0.25*category + 0.15*recency(exp(-age_h/72)) + 0.10*urgency(<6h left & stock>0)`. Weights live in a config row. It falls back to distance-only, and to an area/city picker if location is denied.
8. `PaymentProvider` and `RiskScorer` interfaces. RiskScorer defaults to always-allow; an ML fraud model is Phase 2.
9. Every admin/financial state change writes an append-only `audit_log` (actor, action, before/after).
10. Edge Functions are stateless; retry-prone work (expiry, reconciliation, notifications, reminders) runs from DB events and scheduled jobs.

## 5. Data model (tables)
`profiles`, `user_roles`, `merchants` (PostGIS `geography(Point,4326)`, GiST index, `verification_status`), `deals` (draft > pending > active > rejected/ended; sale window separate from `redeem_window_days`), `orders` (incl. kind `tip`; `expires_at` reservation ~10 min), `payments` (unique `webhook_event_id`), `refunds`, `vouchers` (unique code, `merchant_id` copied from the deal, `valid_until`), `appointment_slots`, `bookings`, `reviews` (unique `voucher_id`), `reward_ledger` (append-only; balance derived), `payouts`, `audit_log`.

Other indexes: `deals(status, ends_at)`, `vouchers(merchant_id, status)`, `bookings(slot_id)`.

## 6. Modules and Edge Functions
- **Auth & profile:** `signup-complete`, `set-role-request` (merchant role granted only after admin approval).
- **Deals & discovery:** `deals-nearby`, `deal-detail`, `deal-create`, `deal-submit`.
- **Orders & payments:** `create-order`, `payment-webhook`, `refund-request`.
- **Vouchers:** `voucher-list`, `redeem-voucher` (signed QR payload).
- **Bookings:** `slots-list`, `booking-create`, `booking-cancel`.
- **Rewards & reviews:** `review-create`, `points-redeem`.
- **Notifications:** DB trigger > queue > send (push + email).
- **Admin & analytics:** `approve-merchant`, `approve-deal`, `decide-refund`, `run-payouts`, `stats`.

API conventions: HTTPS + bearer JWT, errors as `{error:{code,message}}`, cursor pagination (max 50), Idempotency-Key on money/stock mutations.

## 7. State machines (design target)
- **Order:** pending > paid | expired | refund_required; expired > paid (late payment, unit free) | refund_required; paid > refunded.
- **Voucher:** active > redeemed | expired | refund_pending; refund_pending > refunded | active.
- **Deal:** draft > pending > active | rejected; active > ended; active > pending on merchant edit.
- **Booking:** confirmed > completed | cancelled.

## 8. Requirements (IDs used across all docs)
- **Consumer:** FR-C1 register/profile; C2 search/filter nearby; C3 purchase + QR voucher; C4 single-use redemption; C5 review/tip; C6 appointment booking; C7 reward points; C8 saved searches/alerts (**Phase 2**).
- **Merchant:** FR-M1 onboarding + verification docs; M2 create/submit deals; M3 scan/enter voucher; M4 slots/calendar; M5 sales dashboard.
- **Admin:** FR-A1 approve merchants/deals/refunds; A2 moderation/account mgmt; A3 platform analytics.
- **Discovery/Platform:** FR-D1 weighted ranking; D2 cold-start fallback; P1 UPI payments incl. failure/refund; P2 notifications; P3 one REST contract for all clients.
- **Non-functional:** NFR-1 voucher validation < ~200 ms; 2 independently scalable domains; 3 single JWT auth; 4 RBAC; 5 pluggable fraud scorer; 6 works with sparse data; 7 tolerates missing/imprecise location; 8 per-merchant config in a shared schema; 9 audit log; 10 shared API/types.

## 9. Scope
- **MVP (this project):** discover, buy, redeem, book, rewards, merchant and admin tools.
- **Phase 2:** deal alerts, saved searches, personalised ranking, ML fraud detection, WhatsApp, regional languages.
- **Later:** referrals, subscriptions, promoted placements, flash deals, automatic PSP split settlement (payouts are manual/admin-run in v1).

## 10. Literature (10 IEEE papers, all in Downloads as PDFs)
Vas 2023 (hyperlocal), Satrio 2022 (MVP features), Chang 2010 (marketplace-as-a-service / multi-tenancy), Kohli 2024 and de O. Junior 2022 (microservices/auth), Sharma 2015, Lin 2018, Tong 2017, Cecil 2024 (location recommenders), Lingareddy 2025 (UPI fraud, DQN+XGBoost). Identified gaps: no work covers vouchers + QR redemption + appointments together; recommenders need history that a new platform lacks; fraud-model results are untested outside public datasets.

## 11. Current implementation state (checkpoint of 29 Oct 2026)
Existing prototype: `NextTo_Codebase.zip` (Downloads; **not yet unpacked into major_project**) plus an earlier `NextTo_Deals_Module.zip`.

**What exists (a Node 22 prototype with no dependencies):**
- `OrderService` (create-order, handleCallback, requestRefund, decideRefund, reconcile).
- Simulated provider with HMAC-SHA256 and a `RiskScorer` that always allows.
- Neighbouring services: deals, vouchers, rewards, bookings, notifications, admin, auth.
- HTTP server, one basic `web/index.html`, `db/migrations/001_core.sql`, and 69 `node:test` tests (98.57% line / 91.37% branch coverage).
- The deals module had its own 4 test files and a radius/approval demo.

**What is simulated or missing:**
- In-memory store, not a database. The SQL migration and RLS policies were written but **never run**.
- Login is a dev OTP with a self-signed token, not Supabase Auth.
- No live Razorpay/Cashfree.
- **Not started:** Expo consumer and merchant apps, admin dashboard, CI pipeline, Edge Functions, Realtime, Storage/doc upload, push/email, payouts, and the GitHub repo (no repo link yet).

## 12. Known mismatches to resolve before building
The prototype's behaviour differs from the system design in these places:
1. **Stock reservation:** the design reserves stock at order creation (10-min expiry job). The prototype decrements stock at payment confirmation.
2. **Order states:** the design has `expired` and `refund_required`. The prototype has pending/paid/failed/refunded.
3. **Pending timeout:** the design says 10 min for reservation expiry; the proposal and prototype use 15 min for reconciliation. They need not conflict (expiry vs reconcile) but should be stated clearly.
4. **Reward points:** the design credits points at redemption (so there is nothing to reverse on refund). The prototype ties points to payment and reverses them on refund.
5. **Paid-but-sold-out:** the prototype fails the order and queues a refund; the design retries the reservation, then sets `refund_required` and auto-refunds.
6. **Refund flow:** the design has the voucher go to `refund_pending` (blocks redemption during review). The prototype requires an active voucher and an admin decision, and needs checking against the `refund_pending` step.
7. **Extra behaviours added in code** (provider outage retry, refund retry, late events, out-of-stock refund) are not yet in the design docs.
8. **Atomicity:** the design puts all of this in PostgreSQL functions via `rpc()`. The prototype uses in-memory transactions, so the logic must be re-implemented as SQL functions.
9. **Proposal gaps:** several fields are unfilled (course, guide designation/email, coordinator, other team members, payment details). The patent search is pending. Tax/invoicing is unconfirmed. Whether merchants get staff accounts is undecided.

## 13. Open decisions
- Razorpay vs Cashfree (adapter is swappable; the prototype is provider-agnostic).
- SMS provider for phone OTP in India (email sign-in is the fallback).
- Merchant staff accounts (owner only vs staff roles).
- Tax/invoicing requirements for deal sales (confirm with the guide).
- Repo structure: monorepo (apps/mobile, apps/web, apps/admin, packages/types, supabase/) is the likely fit for the shared types package.
- Porting approach for the existing prototype: keep the JS business rules as the spec/test oracle and re-implement them as SQL functions + TypeScript Edge Functions.

## 14. Source files (all in `C:\Users\kartik\Downloads`)
- Design: `NextTo_System_Design_Specification.docx` (latest, most complete), `NextTo_System_Design_Document.docx`, `System_Design.pdf`, `System Design (2).pdf`, `Detailed Design Document - NextTo.docx`
- Requirements/survey: `NextTo_Literature_Survey_Requirements_v2.docx` (latest), `Literature_Survey*.pdf`, `NextTo_Project_Context.md` (older, 7 Oct)
- Proposal/deck: `NextTo_KSCST_SPP_Project_Proposal.docx/.pdf`, `NextTo_Presentation.pptx`
- Weekly reports: `Week1..Week8_Task*_Leah.docx/.pptx`, `NextTo_Task4_Core_Implementation_Orders_and_Payments.docx`
- Code: `NextTo_Codebase.zip`, `NextTo_Deals_Module.zip`
- Papers: the 10 IEEE PDFs

_Not read:_ the unrelated Downloads files (personal documents, other-course PDFs, other zips) were ignored.

---

## 15. UPDATE 13 Nov 2026 (evening): decisions made and build status
**Stack changed by the user (supersedes sections 3, 4 and 12 where they conflict):** React (Vite + TypeScript) front end, **FastAPI + SQLite** back end, mobile app deferred: consumer and merchant screens are a mobile-first responsive web app (phone-width on any browser). Phone OTP replaced with email + password. The old Supabase / Expo / Edge Functions design is the Phase-2 migration. Two new templates were imported: `Project Report Template.docx` and `Project_Presentation_Template.pptx` (Phase-1 review, about 70% target); filled versions are generated into `docs/`.

**Built (all in this folder):** `backend/` (FastAPI: auth, discovery + ranking, orders, signed webhook, vouchers, refunds, bookings, reviews/tips, rewards, merchant, admin, payouts, audit, scheduled expiry and reconciliation; 74 pytest tests passing), `frontend/` (consumer, merchant and admin UIs), `scripts/e2e_demo.py` (21-step live journey, passes), `README.md`, `run.bat`, `docs/DEMO_SCRIPT.md`.
**Resolved mismatches (code follows the design doc):** stock is reserved at order creation (10-minute expiry); order states include `expired` and `refund_required`; refund goes through `refund_pending`; points are credited at redemption (and spent points are restored on refund/expiry).
**Still open:** live Razorpay/Cashfree test keys; native Expo apps; Postgres/Supabase migration; push/email delivery; ML fraud scorer; CI pipeline; pilot with merchants.
