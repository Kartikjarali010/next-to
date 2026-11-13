import { Ic } from "./icons";
import { useEffect, useState } from "react";

let deferred: any = null;
const listeners = new Set<() => void>();
if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferred = e; listeners.forEach((l) => l()); });
  window.addEventListener("appinstalled", () => { deferred = null; listeners.forEach((l) => l()); });
}
const standalone = () => window.matchMedia("(display-mode: standalone)").matches || (navigator as any).standalone === true;

/** "Install app" banner for shoppers: native prompt on Android Chrome, instructions on iOS Safari. */
export function InstallBanner() {
  const [, tick] = useState(0);
  const [hidden, setHidden] = useState(() => { try { return localStorage.getItem("nt_install_hidden") === "1"; } catch { return false; } });
  useEffect(() => { const l = () => tick((n) => n + 1); listeners.add(l); return () => { listeners.delete(l); }; }, []);
  if (hidden || standalone()) return null;
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  if (!deferred && !ios) return null;
  const close = () => { setHidden(true); try { localStorage.setItem("nt_install_hidden", "1"); } catch {} };
  return (
    <div className="card flat row" style={{ borderColor: "var(--brand)" }}>
      <img src="/icon-192.png" width={40} height={40} alt="" style={{ borderRadius: 10 }} />
      <div className="grow"><b>Install the NextTo app</b>
        <div className="small muted">{ios ? "Tap Share, then “Add to Home Screen”." : "Opens full screen, like a real app."}</div></div>
      {deferred && <button className="btn sm" onClick={async () => { deferred.prompt(); await deferred.userChoice; deferred = null; listeners.forEach((l) => l()); }}>Install</button>}
      <button className="btn sm light" onClick={close} aria-label="Dismiss"><Ic n="close" size={16} /></button>
    </div>
  );
}
