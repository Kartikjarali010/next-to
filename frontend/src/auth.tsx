import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from "react";
import { api, getToken, setToken } from "./api";

export interface User { id: number; email: string; name: string; role: "consumer" | "merchant" | "merchant_applicant" | "admin"; points?: number; merchant?: { id: number; name: string; verification_status: string; reject_reason?: string } }
interface Ctx { user: User | null; loading: boolean; login(email: string, password: string): Promise<User>; signup(body: any): Promise<User>; logout(): void; reload(): Promise<void>; refreshToken(): Promise<User | null> }
const C = createContext<Ctx>(null as any);
export const useAuth = () => useContext(C);
export const homeFor = (u: User) => u.role === "admin" ? "/admin" : u.role === "merchant" || u.role === "merchant_applicant" ? "/merchant" : "/";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    if (!getToken()) { setUser(null); setLoading(false); return; }
    try { setUser(await api<User>("/auth/me")); } catch { setToken(null); setUser(null); }
    setLoading(false);
  }, []);
  useEffect(() => { reload(); }, [reload]);
  const take = (r: { token: string; user: User }) => { setToken(r.token); setUser(r.user); return r.user; };
  return (
    <C.Provider value={{
      user, loading, reload,
      login: async (email, password) => take(await api("/auth/login", { body: { email, password } })),
      signup: async (body) => take(await api("/auth/signup", { body })),
      logout: () => { setToken(null); setUser(null); },
      refreshToken: async () => { try { return take(await api("/auth/refresh", { method: "POST", body: {} })); } catch { return null; } },
    }}>{children}</C.Provider>
  );
}
