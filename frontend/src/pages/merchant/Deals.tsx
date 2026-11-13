import { Photo } from "../../images";
import { Ic } from "../../icons";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtDate, money } from "../../api";
import { Badge, CATEGORY_BG, CATEGORY_ICON, Empty, ErrorBox, Spinner, useAsync, useToast } from "../../components";

export default function Deals() {
  const toast = useToast();
  const { data, loading, error, reload } = useAsync(() => api<any[]>("/merchant/deals"));
  const [busy, setBusy] = useState<number | null>(null);

  const submit = async (id: number) => {
    setBusy(id);
    try { await api(`/merchant/deals/${id}/submit`, { method: "POST", body: {} }); toast("Submitted for approval"); reload(); }
    catch (e: any) { toast(e.message, "err"); }
    setBusy(null);
  };

  return (
    <div className="stack">
      <div className="row between"><h1>My deals</h1><Link to="/merchant/deals/new" className="btn sm">+ New deal</Link></div>
      <div className="alert warn small">Editing a live deal sends it back to <b>pending</b> for re-approval.</div>
      {loading ? <Spinner /> : error ? <ErrorBox error={error} retry={reload} /> : !data?.length ? <Empty icon="tag">No deals yet. Create your first one!</Empty> :
        data.map((d) => (
          <div key={d.id} className="card stack-s">
            <div className="row">
              <Photo src={d.image_url} category={d.category} alt={d.title} className="mini-photo" />
              <div className="grow"><div className="bold">{d.title}</div><div className="small muted">{d.type} · {d.category}</div></div>
              <Badge s={d.status} />
            </div>
            <div className="row between small">
              <span><b>{money(d.price)}</b> <span className="strike">{money(d.original_price)}</span></span>
              <span>Stock {d.stock_remaining}/{d.stock_total} · sold {d.sold}</span>
            </div>
            <div className="small muted">{fmtDate(d.starts_at)} – {fmtDate(d.ends_at)}</div>
            {d.status === "rejected" && d.reject_reason && <div className="alert err small">Rejected: {d.reject_reason}</div>}
            <div className="row">
              <Link to={`/merchant/deals/${d.id}`} className="btn sm ghost">Edit</Link>
              {(d.status === "draft" || d.status === "rejected") &&
                <button className="btn sm" disabled={busy === d.id} onClick={() => submit(d.id)}>Submit for approval</button>}
            </div>
          </div>))}
    </div>
  );
}
