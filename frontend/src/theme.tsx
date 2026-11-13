import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { Ic } from "./icons";

/** Light / dark theme. Follows the device setting until the user picks one; the choice is remembered. */
type Mode = "light" | "dark";
const Ctx = createContext<{ mode: Mode; toggle: () => void }>({ mode: "light", toggle: () => {} });
export const useTheme = () => useContext(Ctx);

const systemMode = (): Mode => (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
const stored = (): Mode | null => { try { const v = localStorage.getItem("nt_theme"); return v === "dark" || v === "light" ? v : null; } catch { return null; } };

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(() => stored() ?? systemMode());
  useEffect(() => {
    document.documentElement.dataset.theme = mode;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", mode === "dark" ? "#0b1220" : "#0f766e");
  }, [mode]);
  useEffect(() => {          // follow the device until the user has chosen
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => { if (!stored()) setMode(systemMode()); };
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  const toggle = () => setMode((m) => {
    const n: Mode = m === "dark" ? "light" : "dark";
    try { localStorage.setItem("nt_theme", n); } catch {}
    return n;
  });
  return <Ctx.Provider value={{ mode, toggle }}>{children}</Ctx.Provider>;
}

export function ThemeToggle({ className = "btn sm", label = false }: { className?: string; label?: boolean }) {
  const { mode, toggle } = useTheme();
  const text = mode === "dark" ? "Light mode" : "Dark mode";
  return (
    <button type="button" className={className} onClick={toggle} aria-label={text} title={text}>
      <Ic n={mode === "dark" ? "sun" : "moon"} size={16} />{label && <span style={{ marginLeft: 6 }}>{text}</span>}
    </button>
  );
}
