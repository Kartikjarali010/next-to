import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth";

const DEMOS = [
  ["Consumer", "kartik@demo.com", "demo123"],
  ["Merchant", "cafe@demo.com", "demo123"],
  ["Admin", "admin@nextto.dev", "admin123"],
];

export default function Login() {
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
        <div style={{ fontSize: "2.6rem" }}>📍</div>
        <h1 style={{ color: "#fff" }}>NextTo</h1>
        <div>Deals next to you. Pay by UPI, redeem in person.</div>
      </div>
      <form className="card stack" onSubmit={submit}>
        <h2>Sign in</h2>
        <div className="field"><label>Email</label><input className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
        <div className="field"><label>Password</label><input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></div>
        {err && <div className="alert err">{err}</div>}
        <button className="btn block" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <div className="center small">New here? <Link to="/signup">Create an account</Link></div>
      </form>
      <div className="card flat stack-s" style={{ marginTop: 14 }}>
        <div className="small muted bold">DEMO ACCOUNTS (tap to sign in)</div>
        <div className="row wrap">
          {DEMOS.map(([label, em, pw]) => <button key={em} type="button" className="chip" onClick={() => submit(undefined, em, pw)}>{label}</button>)}
        </div>
      </div>
      <div className="center small muted" style={{ marginTop: 10 }}><Link to="/">Browse deals without signing in</Link></div>
    </div></div>
  );
}
