import { PhotoPicker } from "../../images";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, fmtDate } from "../../api";
import { Spinner, useAsync, useToast } from "../../components";

const pad = (n: number) => String(n).padStart(2, "0");
const toLocal = (iso: string) => { const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const toIso = (local: string) => new Date(local).toISOString();

function Slots({ dealId }: { dealId: number }) {
  const toast = useToast();
  const { data, loading, reload } = useAsync(() => api<any[]>(`/merchant/deals/${dealId}/slots`), [dealId]);
  const [at, setAt] = useState("");
  const [cap, setCap] = useState("2");
  const add = async () => {
    if (!at) return toast("Pick a date and time", "err");
    try { await api(`/merchant/deals/${dealId}/slots`, { body: { starts_at: toIso(at), capacity: parseInt(cap) || 1 } }); toast("Slot added"); setAt(""); reload(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <div className="card stack">
      <h3>Appointment slots</h3>
      {loading ? <Spinner /> : !data?.length ? <div className="muted small">No slots yet.</div> :
        data.map((s) => <div key={s.id} className="row between small"><span>{fmtDate(s.starts_at)}</span><span className="badge brand">{s.booked_count}/{s.capacity} booked</span></div>)}
      <div className="divider" />
      <div className="field"><label>New slot</label><input className="input" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} /></div>
      <div className="field"><label>Capacity</label><input className="input" type="number" min={1} value={cap} onChange={(e) => setCap(e.target.value)} /></div>
      <button type="button" className="btn light" onClick={add}>+ Add slot</button>
    </div>
  );
}

export default function DealForm() {
  const { id } = useParams();
  const editing = !!id;
  const nav = useNavigate();
  const toast = useToast();
  const meta = useAsync(() => api<{ categories: string[] }>("/meta"));
  const all = useAsync(() => (editing ? api<any[]>("/merchant/deals") : Promise.resolve([])), [id]);
  const [status, setStatus] = useState<string>("");
  const [f, setF] = useState({
    title: "", description: "", category: "cafe", type: "voucher", price: "", original_price: "", stock_total: "20",
    starts_at: toLocal(new Date().toISOString()), ends_at: toLocal(new Date(Date.now() + 7 * 864e5).toISOString()), redeem_window_days: "30", image_url: "",
  });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const d = all.data?.find((x) => String(x.id) === id);
    if (d) {
      setStatus(d.status);
      setF({ title: d.title, description: d.description || "", category: d.category, type: d.type, price: String(d.price), original_price: String(d.original_price),
        stock_total: String(d.stock_total), starts_at: toLocal(d.starts_at), ends_at: toLocal(d.ends_at), redeem_window_days: String(d.redeem_window_days), image_url: d.image_url || "" });
    }
  }, [all.data, id]);

  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });

  const save = async (submit: boolean) => {
    setErr(""); setBusy(true);
    try {
      const body = { ...f, price: parseFloat(f.price), original_price: parseFloat(f.original_price), stock_total: parseInt(f.stock_total),
        redeem_window_days: parseInt(f.redeem_window_days), starts_at: toIso(f.starts_at), ends_at: toIso(f.ends_at), image_url: f.image_url || null };
      if (isNaN(body.price) || isNaN(body.original_price) || isNaN(body.stock_total)) throw new Error("Enter valid price, original price and stock");
      const saved = editing ? await api<any>(`/merchant/deals/${id}`, { method: "PUT", body }) : await api<any>("/merchant/deals", { body });
      if (submit) { await api(`/merchant/deals/${saved.id}/submit`, { method: "POST", body: {} }); toast("Submitted for approval"); }
      else toast(editing && saved.status === "pending" ? "Saved — back in review" : "Saved");
      if (!editing && f.type === "service" && !submit) nav(`/merchant/deals/${saved.id}`, { replace: true });
      else nav("/merchant/deals");
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };

  if (editing && all.loading) return <Spinner />;
  const submittable = !editing || status === "draft" || status === "rejected";

  return (
    <div className="stack">
      <h1>{editing ? "Edit deal" : "New deal"}</h1>
      {status === "active" && <div className="alert warn small">This deal is live. Saving changes returns it to <b>pending</b> for re-approval.</div>}
      <form className="card stack" onSubmit={(e) => { e.preventDefault(); save(false); }}>
        <div className="field"><label>Title</label><input className="input" value={f.title} onChange={set("title")} required minLength={3} /></div>
        <div className="field"><label>Description</label><textarea className="input" value={f.description} onChange={set("description")} /></div>
        <div className="grid2">
          <div className="field"><label>Category</label><select className="input" value={f.category} onChange={set("category")}>{(meta.data?.categories || ["cafe"]).map((c) => <option key={c}>{c}</option>)}</select></div>
          <div className="field"><label>Type</label><select className="input" value={f.type} onChange={set("type")}><option value="voucher">Voucher</option><option value="service">Service (appointment)</option></select></div>
        </div>
        <div className="grid2">
          <div className="field"><label>Deal price (₹)</label><input className="input" inputMode="decimal" value={f.price} onChange={set("price")} required /></div>
          <div className="field"><label>Original price (₹)</label><input className="input" inputMode="decimal" value={f.original_price} onChange={set("original_price")} required /></div>
        </div>
        <div className="grid2">
          <div className="field"><label>Stock</label><input className="input" type="number" min={1} value={f.stock_total} onChange={set("stock_total")} required /></div>
          <div className="field"><label>Redeem within (days)</label><input className="input" type="number" min={1} max={365} value={f.redeem_window_days} onChange={set("redeem_window_days")} required /></div>
        </div>
        <div className="field"><label>Sale starts</label><input className="input" type="datetime-local" value={f.starts_at} onChange={set("starts_at")} required /></div>
        <div className="field"><label>Sale ends</label><input className="input" type="datetime-local" value={f.ends_at} onChange={set("ends_at")} required /></div>
        <div className="field"><label>Deal photo</label><PhotoPicker value={f.image_url} category={f.category} onChange={(v) => setF({ ...f, image_url: v })} /></div>
        {f.type === "service" && !editing && <div className="alert info small">Save the draft first, then add appointment slots.</div>}
        {err && <div className="alert err">{err}</div>}
        <button className="btn light block" disabled={busy}>{busy ? "Saving…" : "Save draft"}</button>
        {submittable && <button type="button" className="btn block" disabled={busy} onClick={() => save(true)}>Save &amp; submit for approval</button>}
      </form>
      {editing && f.type === "service" && <Slots dealId={parseInt(id!)} />}
    </div>
  );
}
