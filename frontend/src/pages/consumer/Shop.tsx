import { Link, useParams } from "react-router-dom";
import { Ic, Stars } from "../../icons";
import { api, fmtDay } from "../../api";
import { Empty, ErrorBox, Spinner, useAsync } from "../../components";
import { Photo } from "../../images";
import DealCard from "./DealCard";
import DealMap from "./DealMap";

/** Shopper-facing merchant profile: photo, about, hours, address, live deals and verified reviews. */
export default function Shop() {
  const { id } = useParams();
  const { data: s, loading, error, reload } = useAsync(() => api<any>(`/shops/${id}`), [id]);
  if (loading) return <Spinner />;
  if (error) return <div className="stack"><ErrorBox error={error} retry={reload} /><Link to="/"><Ic n="back" size={14} /> Back to deals</Link></div>;
  if (!s) return <Empty>Shop not found</Empty>;
  return (
    <div className="stack">
      <Link to="/" className="small"><Ic n="back" size={14} /> All deals</Link>
      <div className="card shop-head">
        <Photo src={s.image_url} category={s.category} alt={s.name} className="shop-cover" />
        <div className="shop-info stack-s">
          <div className="row between wrap">
            <h1 style={{ margin: 0 }}>{s.name}</h1>
            <span className="badge brand"><Ic n="check" size={12} /> Verified shop</span>
          </div>
          <div className="row wrap small" style={{ gap: 8 }}>
            <span className="badge">{s.category}</span>
            {s.rating ? <span className="row" style={{ gap: 4 }}><Ic n="star" size={14} fill="currentColor" className="amber" /><b>{s.rating}</b><span className="muted">({s.review_count} review{s.review_count === 1 ? "" : "s"})</span></span> : <span className="muted">No reviews yet</span>}
            {s.redeemed_count > 0 && <span className="muted">· {s.redeemed_count} voucher{s.redeemed_count === 1 ? "" : "s"} redeemed</span>}
          </div>
          {s.description && <p style={{ margin: 0 }}>{s.description}</p>}
          <div className="small"><Ic n="pin" size={14} /> {s.address}</div>
          {s.hours && <div className="small"><Ic n="clock" size={14} /> {s.hours}</div>}
        </div>
      </div>

      <h2 style={{ marginBottom: 0 }}>Deals from {s.name}</h2>
      {s.deals.length === 0 ? <Empty icon="tag">No live deals right now.</Empty> :
        s.deals.map((d: any) => <DealCard key={d.id} d={{ ...d, merchant_name: s.name, rating: s.rating, lat: s.lat, lng: s.lng }} />)}

      <div className="card stack-s">
        <h3 className="row"><Ic n="pin" size={18} /> Find us</h3>
        <DealMap center={[s.lat, s.lng]} deals={[{ id: s.id, title: s.name, price: 0, lat: s.lat, lng: s.lng, merchant_name: s.address }]} height={180} />
        <a className="small" href={`https://www.google.com/maps?q=${s.lat},${s.lng}`} target="_blank" rel="noreferrer">Open in Google Maps <Ic n="next" size={12} /></a>
      </div>

      <div className="card stack-s">
        <h3>Reviews</h3>
        {s.reviews.length === 0 ? <div className="small muted">No reviews yet. Reviews come only from verified redemptions.</div> :
          s.reviews.map((r: any, i: number) => (
            <div key={i}><div className="row between"><b className="small">{r.name}</b><Stars n={r.rating} /></div>
              {r.comment && <div className="small">{r.comment}</div>}<div className="small muted">{fmtDay(r.created_at)}</div></div>))}
      </div>
    </div>
  );
}
