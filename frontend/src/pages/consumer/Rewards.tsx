import { api, fmtDate } from "../../api";
import { Empty, ErrorBox, Spinner, useAsync } from "../../components";

const LABEL: Record<string, string> = { earn: "Earned on redemption", redeem: "Spent at checkout", restore: "Points returned" };

export default function Rewards() {
  const { data, loading, error, reload } = useAsync(() => api<any>("/rewards"), []);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  return (
    <div className="stack">
      <div className="hero center">
        <div className="small" style={{ opacity: .9 }}>Your reward points</div>
        <div style={{ fontSize: "2.8rem", fontWeight: 800 }}>⭐ {data.balance}</div>
        <div className="small">Worth ₹{data.balance * data.point_value_rupees} · use up to {data.max_discount_pct}% off any deal</div>
      </div>
      <div className="card flat small muted">Earn 1 point for every ₹10 you spend — credited when the merchant redeems your voucher.</div>
      <h3>History</h3>
      {data.ledger.length === 0 ? <Empty icon="⭐">No points yet. Redeem a voucher to earn some.</Empty> :
        data.ledger.map((l: any, i: number) => (
          <div key={i} className="card row between">
            <div><div className="bold small">{LABEL[l.reason] || l.reason}</div><div className="small muted">{fmtDate(l.created_at)}</div></div>
            <b style={{ color: l.delta > 0 ? "var(--ok)" : "var(--err)" }}>{l.delta > 0 ? "+" : ""}{l.delta}</b>
          </div>))}
    </div>
  );
}
