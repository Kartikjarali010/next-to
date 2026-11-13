import { Ic } from "../icons";
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { homeFor, useAuth } from "../auth";
import { useAsync } from "../components";

function SignupForm({ mode }: { mode: "consumer" | "merchant" }) {
  const { signup } = useAuth();
  const nav = useNavigate();
  const meta = useAsync(() => api<{ categories: string[]; areas: { name: string; lat: number; lng: number }[] }>("/meta"));
  const type = mode;
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [b, setB] = useState({ name: "", category: "cafe", address: "", lat: "13.1147", lng: "77.6340", description: "", doc_note: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const locate = () => navigator.geolocation?.getCurrentPosition(
    (p) => setB((x) => ({ ...x, lat: p.coords.latitude.toFixed(5), lng: p.coords.longitude.toFixed(5) })),
    () => setErr("Could not read your location; enter coordinates manually."));

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      const body: any = { ...f, account_type: type };
      if (type === "merchant") body.business = { ...b, lat: parseFloat(b.lat), lng: parseFloat(b.lng) };
      nav(homeFor(await signup(body)), { replace: true });
    } catch (x: any) { setErr(x.message); }
    setBusy(false);
  };

  return (
    <div className="phone"><div className="phone-in" style={{ padding: 16 }}>
      <h1 style={{ marginTop: 10 }}>{type === "merchant" ? "Register your business" : "Create your account"}</h1>
      <form className="card stack" onSubmit={submit}>
        <div className="field"><label>Your name</label><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required minLength={2} /></div>
        <div className="field"><label>Email</label><input className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required /></div>
        <div className="field"><label>Password (min 6 characters)</label><input className="input" type="password" minLength={6} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required /></div>
        {type === "merchant" && <>
          <div className="divider" /><h3>Business details</h3>
          <div className="field"><label>Business name</label><input className="input" value={b.name} onChange={(e) => setB({ ...b, name: e.target.value })} required minLength={2} /></div>
          <div className="field"><label>Category</label>
            <select className="input" value={b.category} onChange={(e) => setB({ ...b, category: e.target.value })}>{(meta.data?.categories || ["cafe"]).map((c) => <option key={c}>{c}</option>)}</select></div>
          <div className="field"><label>Address</label><input className="input" value={b.address} onChange={(e) => setB({ ...b, address: e.target.value })} required /></div>
          <div className="grid2">
            <div className="field"><label>Latitude</label><input className="input" inputMode="decimal" value={b.lat} onChange={(e) => setB({ ...b, lat: e.target.value })} required /></div>
            <div className="field"><label>Longitude</label><input className="input" inputMode="decimal" value={b.lng} onChange={(e) => setB({ ...b, lng: e.target.value })} required /></div>
          </div>
          <button type="button" className="btn light sm" onClick={locate}><Ic n="locate" size={16} /> Use my current location</button>
          <div className="field"><label>About your business</label><textarea className="input" value={b.description} onChange={(e) => setB({ ...b, description: e.target.value })} /></div>
          <div className="field"><label>Verification documents (GST / licence number)</label><input className="input" value={b.doc_note} onChange={(e) => setB({ ...b, doc_note: e.target.value })} /></div>
          <div className="alert info small">An admin reviews your business before you can publish deals.</div>
        </>}
        {err && <div className="alert err">{err}</div>}
        <button className="btn block" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        <div className="center small">Already registered? <Link to={type === "merchant" ? "/merchant/login" : "/login"}>Sign in</Link></div>
      </form>
    </div></div>
  );
}

export default function Signup() { return <SignupForm mode="consumer" />; }
export function MerchantSignup() { return <SignupForm mode="merchant" />; }
