import { api, fmtDay } from "../../api";
import { Badge, Empty, ErrorBox, Spinner, useAsync } from "../../components";

export default function Bookings() {
  const { data, loading, error, reload } = useAsync(() => api<any[]>("/merchant/bookings"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  const groups: Record<string, any[]> = {};
  (data || []).forEach((b) => { (groups[b.starts_at.slice(0, 10)] ||= []).push(b); });
  const days = Object.keys(groups).sort();
  return (
    <div className="stack">
      <h1>Bookings</h1>
      {!days.length ? <Empty icon="📅">No upcoming bookings</Empty> : days.map((day) => (
        <div key={day} className="stack-s">
          <div className="bold muted small">{fmtDay(day + "T12:00:00Z").toUpperCase()}</div>
          {groups[day].map((b) => (
            <div key={b.id} className="card row">
              <div className="bold" style={{ minWidth: 62 }}>{new Date(b.starts_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}</div>
              <div className="grow"><div className="bold">{b.deal_title}</div><div className="small muted">{b.consumer_name} · {b.voucher_code}</div></div>
              <Badge s={b.status} />
            </div>))}
        </div>))}
    </div>
  );
}
