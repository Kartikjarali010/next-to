import { ReactNode } from "react";
import { BrowserRouter, Navigate, NavLink, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import { AuthProvider, homeFor, useAuth } from "./auth";
import { Spinner, ToastProvider } from "./components";
import Login, { AdminLogin, MerchantLogin } from "./pages/Login";
import Signup, { MerchantSignup } from "./pages/Signup";
import { isAppMode, loginPathFor, portalOf } from "./api";
import Home from "./pages/consumer/Home";
import DealDetail from "./pages/consumer/DealDetail";
import Checkout from "./pages/consumer/Checkout";
import Wallet from "./pages/consumer/Wallet";
import VoucherDetail from "./pages/consumer/VoucherDetail";
import Rewards from "./pages/consumer/Rewards";
import Profile from "./pages/consumer/Profile";
import MDashboard from "./pages/merchant/Dashboard";
import MDeals from "./pages/merchant/Deals";
import MDealForm from "./pages/merchant/DealForm";
import MScan from "./pages/merchant/Scan";
import MBookings from "./pages/merchant/Bookings";
import MMore from "./pages/merchant/More";
import AOverview from "./pages/admin/Overview";
import AMerchants from "./pages/admin/Merchants";
import ADeals from "./pages/admin/Deals";
import ARefunds from "./pages/admin/Refunds";
import APayouts from "./pages/admin/Payouts";
import AModeration from "./pages/admin/Moderation";
import AAudit from "./pages/admin/Audit";

/** Gate a route tree by role. Unauthenticated users go to /login. */
function Guard({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to={loginPathFor(portalOf())} replace />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user)} replace />;
  return <>{children}</>;
}

function PhoneShell({ title, tabs }: { title: string; tabs: { to: string; icon: string; label: string; end?: boolean }[] }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="phone"><div className="phone-in">
      <div className="topbar"><span style={{ fontSize: "1.3rem" }}>📍</span><h1 className="grow">{title}</h1><button className="btn sm" onClick={() => { logout(); nav("/login"); }}>{user?.name.split(" ")[0]} · Sign out</button></div>
      <div className="content"><Outlet /></div>
      <nav className="tabbar">{tabs.map((t) => <NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) => (isActive ? "active" : "")}><span className="ic">{t.icon}</span>{t.label}</NavLink>)}</nav>
    </div></div>
  );
}

const ConsumerShell = () => <PhoneShell title="NextTo" tabs={[
  { to: "/", icon: "🔍", label: "Discover", end: true }, { to: "/wallet", icon: "🎟️", label: "Wallet" },
  { to: "/rewards", icon: "⭐", label: "Points" }, { to: "/profile", icon: "👤", label: "Profile" }]} />;

/** Merchant and admin are desktop web apps (sidebar layout); only the consumer side is a phone-width app. */
function WebShell({ title, links }: { title: string; links: [string, string, boolean?][] }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="adm">
      <aside className="adm-side">
        <h2>{title}</h2>
        {links.map(([to, label, end]) => <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>{label}</NavLink>)}
        <a href="#" onClick={(e) => { e.preventDefault(); logout(); nav(loginPathFor(portalOf())); }}>🚪 Sign out ({user?.name.split(" ")[0]})</a>
      </aside>
      <main className="adm-main"><div className="page"><Outlet /></div></main>
    </div>
  );
}

function MerchantShell() {
  const { user } = useAuth();
  const dash: [string, string, boolean] = ["/merchant", "📊 Dashboard", true];
  // applicants (not yet approved) only see the verification status screen
  if (user?.role === "merchant_applicant") {
    if (location.pathname !== "/merchant") return <Navigate to="/merchant" replace />;
    return <WebShell title="📍 NextTo Business" links={[dash]} />;
  }
  return <WebShell title="📍 NextTo Business" links={[dash, ["/merchant/deals", "🏷️ Deals"], ["/merchant/scan", "📷 Redeem voucher"], ["/merchant/bookings", "📅 Bookings"], ["/merchant/more", "👤 Account & payouts"]]} />;
}

function AdminShell() {
  return <WebShell title="📍 NextTo Admin" links={[["/admin", "📈 Overview", true], ["/admin/merchants", "🏪 Merchants"], ["/admin/deals", "🏷️ Deals"], ["/admin/refunds", "↩️ Refunds"], ["/admin/payouts", "💸 Payouts"], ["/admin/moderation", "🛡️ Moderation"], ["/admin/audit", "📜 Audit log"]]} />;
}

function Root() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  return <ConsumerShell />;
}

/** The Android app and the installed phone app are shopper-only: business portals are not reachable from them. */
function WebOnly({ children }: { children: ReactNode }) {
  return isAppMode() ? <Navigate to="/" replace /> : <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider><ToastProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/merchant/login" element={<WebOnly><MerchantLogin /></WebOnly>} />
          <Route path="/merchant/signup" element={<WebOnly><MerchantSignup /></WebOnly>} />
          <Route path="/admin/login" element={<WebOnly><AdminLogin /></WebOnly>} />
          {/* consumer: browsing deals is public; wallet/profile/checkout require login */}
          <Route element={<Root />}>
            <Route index element={<Home />} />
            <Route path="deal/:id" element={<DealDetail />} />
            <Route path="checkout/:id" element={<Guard roles={["consumer"]}><Checkout /></Guard>} />
            <Route path="wallet" element={<Guard roles={["consumer"]}><Wallet /></Guard>} />
            <Route path="voucher/:id" element={<Guard roles={["consumer"]}><VoucherDetail /></Guard>} />
            <Route path="rewards" element={<Guard roles={["consumer"]}><Rewards /></Guard>} />
            <Route path="profile" element={<Guard roles={["consumer"]}><Profile /></Guard>} />
          </Route>
          <Route path="merchant" element={<WebOnly><Guard roles={["merchant", "merchant_applicant"]}><MerchantShell /></Guard></WebOnly>}>
            <Route index element={<MDashboard />} />
            <Route path="deals" element={<MDeals />} />
            <Route path="deals/new" element={<MDealForm />} />
            <Route path="deals/:id" element={<MDealForm />} />
            <Route path="scan" element={<MScan />} />
            <Route path="bookings" element={<MBookings />} />
            <Route path="more" element={<MMore />} />
          </Route>
          <Route path="admin" element={<WebOnly><Guard roles={["admin"]}><AdminShell /></Guard></WebOnly>}>
            <Route index element={<AOverview />} />
            <Route path="merchants" element={<AMerchants />} />
            <Route path="deals" element={<ADeals />} />
            <Route path="refunds" element={<ARefunds />} />
            <Route path="payouts" element={<APayouts />} />
            <Route path="moderation" element={<AModeration />} />
            <Route path="audit" element={<AAudit />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ToastProvider></AuthProvider>
    </BrowserRouter>
  );
}
