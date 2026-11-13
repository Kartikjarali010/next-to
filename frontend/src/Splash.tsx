import { useEffect, useState } from "react";
import { Ic } from "./icons";
import { portalOf } from "./api";

/** Branded splash shown once per session when the shopper app opens (not on merchant/admin portals). */
export default function Splash() {
  const show = () => { try { return portalOf() === "consumer" && sessionStorage.getItem("nt_splash") !== "1"; } catch { return false; } };
  const [visible, setVisible] = useState(show);
  const [hide, setHide] = useState(false);
  useEffect(() => {
    if (!visible) return;
    try { sessionStorage.setItem("nt_splash", "1"); } catch {}
    const t1 = setTimeout(() => setHide(true), 1500);
    const t2 = setTimeout(() => setVisible(false), 2050);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [visible]);
  if (!visible) return null;
  return (
    <div className={"splash" + (hide ? " hide" : "")} role="status" aria-label="Loading NextTo">
      <div className="splash-logo"><Ic n="pin" size={52} strokeWidth={2.4} /></div>
      <div className="splash-name">NextTo</div>
      <div className="splash-tag">Deals next to you</div>
      <div className="splash-bar"><i /></div>
    </div>
  );
}
