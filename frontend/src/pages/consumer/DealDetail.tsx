import { Ic, Stars } from "../../icons";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, fmtDate, money, timeLeft } from "../../api";
import { useAuth } from "../../auth";
import { Empty, ErrorBox, Spinner, useAsync } from "../../components";
import { Photo } from "../../images";
import DealMap from "./DealMap";

export default function DealDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const { data: d, loading, error, reload } = useAsync(() => api<any>(`/deals/${id}`), [id]);

  if (loading) return <Spinner />;
  if (error) return <div className="stack"><ErrorBox error={error} retry={reload} /><Link to="/"><Ic n="back" size={14} /> Back to deals</Link></div>;
  if (!d) return <Empty>Deal not found</Empty>;

  const off = Math.round((1 - d.price / d.original_price) * 100);
  const soldOut = d.stock_remaining <= 0;
  const buy = () => {
    if (!user) return nav("/login");
    if (user.role !== "consumer") return;
    nav(`/checkout/${d.id}`);
  };

  return (
    <div className="stack">
      <Link to="/" className="small"><Ic n="back" size={14} /> All deals</Link>
      <div className="card stack">
        <Photo src={d.image_url} category={d.category} alt={d.title} className="deal-hero" />
        <div>
          <h1 style={{ marginBottom: 2 }}>{d.title}</h1>
          <Link to={`/shop/${d.merchant_id}`} className="small row" style={{ gap: 4 }}><Ic n="store" size={14} /> {d.merchant_name} <Ic n="next" size={12} /></Link>
        </div>
        <div className="row wrap">
          <span className="price" style={{ fontSize: "1.6rem" }}>{money(d.price)}</span><span className="strike">{money(d.original_price)}</span>
          {off > 0 && <span className="off">{off}% OFF</span>}
        </div>
        <div className="row wrap small" style={{ gap: 6 }}>
          <span className="badge brand">{d.type === "service" ? "Appointment deal" : "Voucher deal"}</span>
          <span className="badge"><Ic n="hourglass" size={12} /> {timeLeft(d.ends_at)}</span>
          {d.stock_remaining <= 5 && d.stock_remaining > 0 && <span className="badge warn">Only {d.stock_remaining} left</span>}
          {soldOut && <span className="badge err">Sold out</span>}
        </div>
        {d.description && <p style={{ margin: 0 }}>{d.description}</p>}
        <div className="small muted">Valid for {d.redeem_window_days} days after purchase. Single-use QR voucher.</div>
        <button className="btn block" disabled={soldOut || (!!user && user.role !== "consumer")} onClick={buy}>
          {soldOut ? "Sold out" : !user ? "Sign in to buy" : `Buy now · ${money(d.price)}`}
        </button>
        {user && user.role !== "consumer" && <div className="alert warn small">Only shopper accounts can buy deals.</div>}
      </div>

      {d.type === "service" && (
        <div className="card stack-s">
          <h3 className="row"><Ic n="calendar" size={18} /> Available appointment slots</h3>
          <div className="small muted">Buy first, then pick your slot from your voucher.</div>
          {d.slots.length === 0 ? <div className="small">No upcoming slots yet.</div> :
            <div className="chips" style={{ flexWrap: "wrap" }}>{d.slots.map((s: any) => (
              <span key={s.id} className="chip" style={{ cursor: "default", opacity: s.booked_count >= s.capacity ? .4 : 1 }}>
                {fmtDate(s.starts_at)} · {Math.max(0, s.capacity - s.booked_count)} left</span>))}</div>}
        </div>
      )}

      <div className="card stack-s">
        <h3 className="row"><Ic n="pin" size={18} /> {d.merchant_name}</h3>
        <div className="small">{d.merchant_address}</div>
        {d.merchant_description && <div className="small muted">{d.merchant_description}</div>}
        <DealMap center={[d.lat, d.lng]} deals={[{ id: d.id, title: d.title, price: d.price, lat: d.lat, lng: d.lng, merchant_name: d.merchant_name }]} height={180} />
        {d.merchant_hours && <div className="small"><Ic n="clock" size={14} /> {d.merchant_hours}</div>}
        <div className="row wrap"><Link className="btn sm ghost" to={`/shop/${d.merchant_id}`}><Ic n="store" size={14} /> View shop profile</Link>
        <a className="small" href={`https://www.google.com/maps?q=${d.lat},${d.lng}`} target="_blank" rel="noreferrer">Open in Google Maps <Ic n="next" size={12} /></a></div>
      </div>

      <div className="card stack-s">
        <h3>Reviews</h3>
        {d.reviews.length === 0 ? <div className="small muted">No reviews yet — reviews come only from verified redemptions.</div> :
          d.reviews.map((r: any, i: number) => (
            <div key={i}><div className="row between"><b className="small">{r.name}</b><span><Stars n={r.rating} /></span></div>
              {r.comment && <div className="small">{r.comment}</div>}<div className="small muted">{fmtDate(r.created_at)}</div></div>))}
      </div>
    </div>
  );
}
