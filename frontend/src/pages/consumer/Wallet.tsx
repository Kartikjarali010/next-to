import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, fmtDay, money } from "../../api";
import { Badge, CATEGORY_BG, Empty, ErrorBox, Spinner, useAsync } from "../../components";

const TABS: [string, string[]][] = [["Active", ["active", "refund_pending"]], ["Used", ["redeemed"]], ["Other", ["expired", "refunded"]]];

export default function Wallet() {
  const nav = useNavigate();
  const [tab, setTab] = useState(0);
  const v = useAsync(() => api<any[]>("/vouchers"), []);
  const o = useAsync(() => api<any[]>("/orders"), []);
  if (v.loading || o.loading) return <Spinner />;
  if (v.error) return <ErrorBox error={v.error} retry={v.reload} />;
  const list = (v.data || []).filter((x) => TABS[tab][1].includes(x.status));
  const pending = (o.data || []).filter((x) => x.status === "pending" && x.kind === "deal");

  return (
    <div className="stack">
      <h1>My wallet</h1>
      {pending.length > 0 && (
        <div className="card stack-s" style={{ borderLeft: "4px solid var(--accent)" }}>
          <b>Unpaid orders</b>
          {pending.map((p) => (
            <div key={p.id} className="row between"><div className="small"><b>{p.deal_title}</b><div className="muted">{money(p.amount)} · reserved</div></div>
              <button className="btn sm warn" onClick={() => nav(`/checkout/${p.deal_id}?order=${p.id}`)}>Resume payment</button></div>))}
        </div>
      )}
      <div className="row">{TABS.map(([label], i) => <button key={label} className={"chip " + (tab === i ? "on" : "")} onClick={() => setTab(i)}>{label}</button>)}</div>
      {list.length === 0 ? <Empty icon="🎟️">{tab === 0 ? <>No active vouchers. <Link to="/">Find a deal</Link></> : "Nothing here yet."}</Empty> :
        list.map((x) => (
          <div key={x.id} className="card deal" onClick={() => nav(`/voucher/${x.id}`)}>
            <div className="thumb" style={{ background: CATEGORY_BG[x.deal_type === "service" ? "salon" : "cafe"] }}>{x.deal_type === "service" ? "📅" : "🎟️"}</div>
            <div className="grow stack-s">
              <div className="bold">{x.deal_title}</div>
              <div className="small muted">{x.merchant_name}</div>
              <div className="row wrap small" style={{ gap: 6 }}><Badge s={x.status} />
                {x.status === "active" && <span className="muted">valid till {fmtDay(x.valid_until)}</span>}
                {x.booking && <span className="badge info">📅 booked</span>}</div>
            </div>
          </div>))}
    </div>
  );
}
