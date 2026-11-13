import L from "leaflet";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { Link } from "react-router-dom";
import { money } from "../../api";

const pin = (emoji: string, bg: string) => L.divIcon({
  className: "", iconSize: [34, 34], iconAnchor: [17, 17],
  html: `<div style="width:34px;height:34px;border-radius:50%;background:${bg};display:flex;align-items:center;justify-content:center;font-size:18px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35)">${emoji}</div>`,
});

export interface MapDeal { id: number; title: string; price: number; lat: number; lng: number; merchant_name?: string }

export default function DealMap({ center, deals, height }: { center: [number, number]; deals: MapDeal[]; height?: number }) {
  return (
    <MapContainer center={center} zoom={14} scrollWheelZoom style={height ? { height } : undefined}>
      <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Marker position={center} icon={pin("🧍", "#2563eb")}><Popup>You are here</Popup></Marker>
      {deals.map((d) => (
        <Marker key={d.id} position={[d.lat, d.lng]} icon={pin("🏷️", "#0f766e")}>
          <Popup><b>{d.title}</b><br />{d.merchant_name}<br />{money(d.price)}<br /><Link to={`/deal/${d.id}`}>View deal →</Link></Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
