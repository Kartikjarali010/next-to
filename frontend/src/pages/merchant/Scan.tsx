import { Ic } from "../../icons";
import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { api, fmtDate } from "../../api";
import { Badge } from "../../components";

type Preview = { code: string; status: string; valid_until: string; deal_title: string; deal_type: string; consumer_name: string };

export default function Scan() {
  const [raw, setRaw] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [done, setDone] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [camera, setCamera] = useState(false);
  const [camErr, setCamErr] = useState("");
  const scanner = useRef<Html5Qrcode | null>(null);

  const stop = async () => {
    const s = scanner.current;
    scanner.current = null;
    if (s) { try { if (s.isScanning) await s.stop(); s.clear(); } catch { /* ignore */ } }
  };
  useEffect(() => () => { stop(); }, []);

  const lookup = async (text: string) => {
    setErr(""); setDone(null); setPreview(null); setBusy(true);
    try { setPreview(await api<Preview>("/merchant/vouchers/lookup", { body: { code: text } })); setRaw(text); }
    catch (e: any) { setErr(e.message); }
    setBusy(false);
  };

  const startCamera = async () => {
    setCamErr(""); setCamera(true);
    await new Promise((r) => setTimeout(r, 50)); // let the #qr-reader div mount
    try {
      const s = new Html5Qrcode("qr-reader");
      scanner.current = s;
      await s.start({ facingMode: "environment" }, { fps: 10, qrbox: 220 },
        async (text) => { await stop(); setCamera(false); lookup(text); }, () => {});
    } catch {
      setCamera(false); scanner.current = null;
      setCamErr("Camera unavailable or permission denied. Use manual code entry below.");
    }
  };

  const redeem = async () => {
    setBusy(true); setErr("");
    try { setDone(await api("/merchant/vouchers/redeem", { body: { code: raw } })); setPreview(null); }
    catch (e: any) { setErr(e.message); }
    setBusy(false);
  };

  const reset = () => { setRaw(""); setPreview(null); setDone(null); setErr(""); };

  return (
    <div className="stack">
      <h1>Redeem voucher</h1>
      {done ? (
        <div className="card stack center" style={{ background: "var(--ok-l)" }}>
          <div style={{ display: "flex", justifyContent: "center" }}><Ic n="check" size={48} /></div>
          <h2>Redeemed!</h2>
          <div className="bold">{done.deal_title}</div>
          <div className="small">Code {done.code} · {done.points_awarded} points awarded to customer</div>
          <button className="btn block" onClick={reset}>Scan next</button>
        </div>
      ) : (
        <>
          {camera ? (
            <div className="card stack">
              <div id="qr-reader" style={{ width: "100%" }} />
              <button className="btn light" onClick={async () => { await stop(); setCamera(false); }}>Stop camera</button>
            </div>
          ) : (
            <button className="btn block" onClick={startCamera}><Ic n="camera" size={16} /> Scan QR with camera</button>
          )}
          {camErr && <div className="alert warn small">{camErr}</div>}
          <form className="card stack" onSubmit={(e) => { e.preventDefault(); if (raw.trim()) lookup(raw.trim()); }}>
            <div className="field"><label>Or enter code manually</label>
              <input className="input" value={raw} onChange={(e) => setRaw(e.target.value)} placeholder="e.g. 7U85HUGEPF" autoCapitalize="characters" /></div>
            <button className="btn light" disabled={busy || !raw.trim()}>Check voucher</button>
          </form>
          {err && <div className="alert err"><b>Cannot redeem.</b> {err}</div>}
          {preview && (
            <div className="card stack">
              <div className="row between"><h2>{preview.deal_title}</h2><Badge s={preview.status} /></div>
              <div className="small">Customer: <b>{preview.consumer_name}</b></div>
              <div className="small">Type: {preview.deal_type} · Valid until {fmtDate(preview.valid_until)}</div>
              {preview.status === "active"
                ? <button className="btn block" style={{ minHeight: 56, fontSize: "1.1rem" }} disabled={busy} onClick={redeem}>Redeem now</button>
                : <div className="alert err">This voucher is {preview.status.replace(/_/g, " ")} and cannot be redeemed.</div>}
              <button className="btn light sm" onClick={reset}>Cancel</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
