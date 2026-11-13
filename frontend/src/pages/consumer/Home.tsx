import { InstallBanner } from "../../install";
import { useEffect, useState } from "react";
import { api } from "../../api";
import { Empty, ErrorBox, Spinner, CATEGORY_ICON, useAsync } from "../../components";
import DealCard, { DealLite } from "./DealCard";
import DealMap from "./DealMap";

interface Meta { categories: string[]; areas: { name: string; lat: number; lng: number }[] }
interface Res { deals: DealLite[]; total: number; radius_km: number; widened: boolean; origin: { lat: number; lng: number } }

export default function Home() {
  const meta = useAsync(() => api<Meta>("/meta"), []);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [geo, setGeo] = useState<"asking" | "ok" | "denied">("asking");
  const [area, setArea] = useState("");
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const [qDeb, setQDeb] = useState("");
  const [radius, setRadius] = useState(5);
  const [view, setView] = useState<"list" | "map">("list");

  useEffect(() => {
    if (!navigator.geolocation) { setGeo("denied"); return; }
    navigator.geolocation.getCurrentPosition(
      (p) => { setCoords({ lat: p.coords.latitude, lng: p.coords.longitude }); setGeo("ok"); },
      () => setGeo("denied"), { timeout: 6000, maximumAge: 300000 });
  }, []);
  useEffect(() => { const t = setTimeout(() => setQDeb(q), 350); return () => clearTimeout(t); }, [q]);

  const ready = geo !== "asking";
  const useArea = geo === "denied" || !coords;
  const res = useAsync(async () => {
    if (!ready) return null;
    const p = new URLSearchParams({ radius_km: String(radius) });
    if (!useArea && coords) { p.set("lat", String(coords.lat)); p.set("lng", String(coords.lng)); }
    else if (area) p.set("area", area);
    if (cat) p.set("category", cat);
    if (qDeb) p.set("q", qDeb);
    return api<Res>("/deals/nearby?" + p.toString());
  }, [ready, useArea, coords, area, cat, qDeb, radius]);

  const r = res.data;
  return (
    <div className="stack">
      <InstallBanner />
      <div className="hero">
        <div className="bold" style={{ fontSize: "1.1rem" }}>Deals next to you 📍</div>
        <div className="small" style={{ opacity: .9 }}>Pay by UPI · get a QR voucher · redeem in person</div>
        <input className="input" style={{ marginTop: 10 }} placeholder="Search cafés, salons, cakes…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {geo === "denied" && (
        <div className="card flat stack-s">
          <div className="small bold">Location unavailable — choose your area</div>
          <select className="input" value={area} onChange={(e) => setArea(e.target.value)}>
            <option value="">Default (Kattigenahalli / REVA)</option>
            {(meta.data?.areas || []).map((a) => <option key={a.name}>{a.name}</option>)}
          </select>
        </div>
      )}
      {geo === "asking" && <div className="small muted center">Finding your location…</div>}

      <div className="chips">
        <span className={"chip " + (!cat ? "on" : "")} onClick={() => setCat("")}>All</span>
        {(meta.data?.categories || []).map((c) => <span key={c} className={"chip " + (cat === c ? "on" : "")} onClick={() => setCat(c)}>{CATEGORY_ICON[c]} {c}</span>)}
      </div>

      <div className="row between">
        <select className="input" style={{ width: "auto" }} value={radius} onChange={(e) => setRadius(+e.target.value)}>
          {[1, 2, 5, 10].map((k) => <option key={k} value={k}>Within {k} km</option>)}
        </select>
        <div className="row" style={{ gap: 6 }}>
          <button className={"btn sm " + (view === "list" ? "" : "light")} onClick={() => setView("list")}>☰ List</button>
          <button className={"btn sm " + (view === "map" ? "" : "light")} onClick={() => setView("map")}>🗺️ Map</button>
        </div>
      </div>

      {res.loading && <Spinner />}
      {res.error && <ErrorBox error={res.error} retry={res.reload} />}
      {r && !res.loading && <>
        {r.widened && <div className="alert info small">No deals within {radius} km, so we widened the search to {r.radius_km} km.</div>}
        {r.deals.length === 0 ? <Empty icon="🔎">No deals found. Try another category or area.</Empty> :
          view === "map"
            ? <DealMap center={[r.origin.lat, r.origin.lng]} deals={r.deals} />
            : <div className="stack">{r.deals.map((d) => <DealCard key={d.id} d={d} />)}</div>}
        {r.deals.length > 0 && <div className="small muted center">{r.total} deal{r.total === 1 ? "" : "s"} ranked by distance, category, freshness &amp; urgency</div>}
      </>}
    </div>
  );
}
