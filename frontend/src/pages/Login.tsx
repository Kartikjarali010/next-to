import { Ic } from "../icons";
import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { isAppMode, Portal } from "../api";
import { homeFor, useAuth } from "../auth";

const PORTALS: Record<Portal, { title: string; sub: string; demos: [string, string, string][]; signup?: string; icon: string }> = {
  consumer: {
    title: "NextTo", sub: "Deals next to you. Pay by UPI, redeem in person.", icon: "pin", signup: "/signup",
    demos: [["Kartik", "kartik@demo.com", "demo123"], ["Leah", "leah@demo.com", "demo123"]],
  },
  merchant: {
    title: "NextTo Business", sub: "Publish deals, scan vouchers, track sales.", icon: "store", signup: "/merchant/signup",
    demos: [["Demo café", "cafe@demo.com", "demo123"], ["Demo salon", "salon@demo.com", "demo123"], ["Pending business", "new@demo.com", "demo123"]],
  },
  admin: {
    title: "NextTo Admin", sub: "Approvals, refunds, payouts and audit.", icon: "shield",
    demos: [["Demo admin", "admin@nextto.dev", "admin123"]],
  },
};

function PortalLogin({ portal }: { portal: Portal }) {
  const cfg = PORTALS[portal];
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to={homeFor(user)} replace />;

  const submit = async (e?: FormEvent, em = email, pw = password) => {
    e?.preventDefault();
    setErr(""); setBusy(true);
    try { nav(homeFor(await login(em, pw)), { replace: true }); }
    catch (x: any) { setErr(x.message); }
    setBusy(false);
  };

  return (
    <div className="phone"><div className="phone-in" style={{ justifyContent: "center", padding: 20 }}>
      <div className="hero center" style={{ marginBottom: 18 }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 4 }}><Ic n={cfg.icon} size={44} /></div>
        <h1 style={{ color: "#fff" }}>{cfg.title}</h1>
        <div>{cfg.sub}</div>
      </div>
      <form className="card stack" onSubmit={submit}>
        <h2>Sign in</h2>
        <div className="field"><label>Email</label><input className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
        <div className="field"><label>Password</label><input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></div>
        {err && <div className="alert err">{err}</div>}
        <button className="btn block" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        {cfg.signup && <div className="center small">New here? <Link to={cfg.signup}>Create an account</Link></div>}
      </form>
      <div className="card flat stack-s" style={{ marginTop: 14 }}>
        <div className="small muted bold">DEMO ACCOUNTS (tap to sign in)</div>
        <div className="row wrap">
          {cfg.demos.map(([label, em, pw]) => <button key={em} type="button" className="chip" onClick={() => submit(undefined, em, pw)}>{label}</button>)}
        </div>
      </div>
      {portal === "consumer" && <>
        <div className="center small muted" style={{ marginTop: 10 }}><Link to="/">Browse deals without signing in</Link></div>
        {!isAppMode() && <div className="center small" style={{ marginTop: 8 }}><a href="/NextTo.apk" download><Ic n="download" size={14} /> Download the Android app (APK)</a></div>}
      </>}
    </div></div>
  );
}

export default function Login() { return <PortalLogin portal="consumer" />; }
export function MerchantLogin() { return <PortalLogin portal="merchant" />; }
export function AdminLogin() { return <PortalLogin portal="admin" />; }
