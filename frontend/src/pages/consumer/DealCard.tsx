import { Ic } from "../../icons";
import { useNavigate } from "react-router-dom";
import { km, money, timeLeft } from "../../api";
import { Photo } from "../../images";

export interface DealLite {
  id: number; title: string; category: string; type: string; price: number; original_price: number;
  stock_remaining: number; ends_at: string; merchant_name: string; rating?: number | null; review_count?: number;
  distance_m?: number; lat: number; lng: number; image_url?: string | null; merchant_id?: number;
}

export default function DealCard({ d }: { d: DealLite }) {
  const nav = useNavigate();
  const off = Math.round((1 - d.price / d.original_price) * 100);
  const hoursLeft = (new Date(d.ends_at).getTime() - Date.now()) / 3600000;
  return (
    <div className="card deal" onClick={() => nav(`/deal/${d.id}`)} role="link">
      <Photo src={d.image_url} category={d.category} alt={d.title} className="deal-photo" />
      <div className="grow stack-s">
        <div className="bold">{d.title}</div>
        <div className="small muted">{d.merchant_name}{d.distance_m !== undefined && <> · <Ic n="pin" size={13} /> {km(d.distance_m)}</>}{d.rating ? <> · <Ic n="star" size={13} fill="currentColor" className="amber" /> {d.rating}</> : null}</div>
        <div className="row wrap" style={{ gap: 6 }}>
          <span className="price">{money(d.price)}</span><span className="strike">{money(d.original_price)}</span>
          {off > 0 && <span className="off">{off}% OFF</span>}
          {d.type === "service" && <span className="badge info">appointment</span>}
        </div>
        <div className="row wrap small" style={{ gap: 6 }}>
          {hoursLeft > 0 && hoursLeft <= 6 && <span className="badge err"><Ic n="urgent" size={12} /> Ending soon</span>}
          <span className="muted">{timeLeft(d.ends_at)}</span>
          {d.stock_remaining <= 5 && <span className="badge warn">Only {d.stock_remaining} left</span>}
        </div>
      </div>
    </div>
  );
}
