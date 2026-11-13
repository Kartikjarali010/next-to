import { useState } from "react";
import { Ic } from "./icons";
import { CATEGORY_ICON } from "./components";

/** Built-in photo library (stock photos from Pexels, see /img/CREDITS.md). Merchants pick from it or paste an https:// link. */
export const PHOTO_LIBRARY: { url: string; label: string; cat: string }[] = [
  { url: "/img/deal-cappuccino.jpg", label: "Cappuccino", cat: "cafe" },
  { url: "/img/deal-coldbrew.jpg", label: "Latte", cat: "cafe" },
  { url: "/img/deal-sandwich.jpg", label: "Sandwich", cat: "cafe" },
  { url: "/img/shop-cafe.jpg", label: "Cafe interior", cat: "cafe" },
  { url: "/img/deal-cake.jpg", label: "Cakes", cat: "bakery" },
  { url: "/img/deal-puffs.jpg", label: "Puffs", cat: "bakery" },
  { url: "/img/deal-bakery2.jpg", label: "Bakery display", cat: "bakery" },
  { url: "/img/deal-brunch.jpg", label: "Brunch", cat: "food" },
  { url: "/img/shop-restaurant.jpg", label: "Thali", cat: "food" },
  { url: "/img/deal-haircut.jpg", label: "Haircut", cat: "salon" },
  { url: "/img/shop-salon.jpg", label: "Salon", cat: "salon" },
  { url: "/img/deal-facial.jpg", label: "Facial", cat: "spa" },
  { url: "/img/deal-gym.jpg", label: "Gym", cat: "fitness" },
  { url: "/img/shop-gym.jpg", label: "Training zone", cat: "fitness" },
  { url: "/img/deal-yoga.jpg", label: "Yoga", cat: "fitness" },
];

const FALLBACK: Record<string, string> = {
  cafe: "/img/deal-coldbrew.jpg", bakery: "/img/deal-bakery2.jpg", food: "/img/shop-restaurant.jpg", salon: "/img/deal-haircut.jpg",
  spa: "/img/deal-facial.jpg", fitness: "/img/deal-gym.jpg", retail: "/img/shop-cafe.jpg", entertainment: "/img/shop-cafe.jpg", services: "/img/shop-cafe.jpg",
};

export const photoFor = (url: string | null | undefined, category: string) => url || FALLBACK[category] || "/img/shop-cafe.jpg";

/** <img> with a graceful fallback to the category icon if the photo cannot load. */
export function Photo({ src, category, alt = "", className = "", style }: { src?: string | null; category: string; alt?: string; className?: string; style?: React.CSSProperties }) {
  const [bad, setBad] = useState(false);
  if (bad) return <div className={"photo-fallback " + className} style={style}><Ic n={CATEGORY_ICON[category] || "tag"} size={32} /></div>;
  return <img className={"photo " + className} style={style} src={photoFor(src, category)} alt={alt} loading="lazy" onError={() => setBad(true)} />;
}

/** Photo chooser used in the merchant deal form and shop profile. */
export function PhotoPicker({ value, onChange, category }: { value: string; onChange: (v: string) => void; category?: string }) {
  const list = category ? [...PHOTO_LIBRARY.filter((p) => p.cat === category), ...PHOTO_LIBRARY.filter((p) => p.cat !== category)] : PHOTO_LIBRARY;
  return (
    <div className="stack-s">
      <div className="photo-grid">
        {list.map((p) => (
          <button type="button" key={p.url} className={"photo-opt" + (value === p.url ? " on" : "")} onClick={() => onChange(value === p.url ? "" : p.url)} title={p.label} aria-label={p.label}>
            <img src={p.url} alt={p.label} loading="lazy" />
            {value === p.url && <span className="photo-tick"><Ic n="check" size={16} /></span>}
          </button>
        ))}
      </div>
      <input className="input" placeholder="…or paste an https:// image link" value={value.startsWith("https://") ? value : ""} onChange={(e) => onChange(e.target.value)} />
      <div className="small muted">{value ? "Photo selected. Tap it again to clear." : "No photo selected: a default photo for the category is shown."}</div>
    </div>
  );
}
