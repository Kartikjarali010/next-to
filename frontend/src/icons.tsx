import {
  AlarmClock, ArrowLeft, ArrowRight, Bell, Banknote, CalendarDays, Camera, CheckCircle2, Clapperboard, Clock, Coffee, Croissant,
  Download, Dumbbell, Flower2, Hourglass, Inbox, Info, LayoutDashboard, List, LocateFixed, LogOut, Map as MapIcon, MapPin,
  PartyPopper, Receipt, RefreshCw, ScanLine, ScrollText, Scissors, Search, ShieldCheck, ShoppingBag, Star, Store, Tag, Ticket,
  TrendingUp, Undo2, User, UserRound, UtensilsCrossed, Wrench, X, XCircle, LucideProps, Moon, Sun,
} from "lucide-react";

const MAP = {
  pin: MapPin, search: Search, ticket: Ticket, star: Star, user: User, person: UserRound, logout: LogOut, dashboard: LayoutDashboard,
  tag: Tag, scan: ScanLine, camera: Camera, calendar: CalendarDays, store: Store, shield: ShieldCheck, refund: Undo2, payout: Banknote,
  audit: ScrollText, chart: TrendingUp, bell: Bell, receipt: Receipt, clock: Clock, hourglass: Hourglass, check: CheckCircle2, cross: XCircle,
  info: Info, party: PartyPopper, list: List, map: MapIcon, download: Download, refresh: RefreshCw, close: X, back: ArrowLeft, next: ArrowRight,
  locate: LocateFixed, inbox: Inbox, urgent: AlarmClock, moon: Moon, sun: Sun,
  // categories
  food: UtensilsCrossed, cafe: Coffee, bakery: Croissant, salon: Scissors, spa: Flower2, fitness: Dumbbell, retail: ShoppingBag,
  entertainment: Clapperboard, services: Wrench,
} as const;

export type IconName = keyof typeof MAP;

/** One icon set (Lucide) used everywhere instead of emoji. */
export function Ic({ n, size = 16, className = "", ...rest }: { n: IconName | string; size?: number; className?: string } & Omit<LucideProps, "size">) {
  const C = (MAP as any)[n] || Tag;
  return <C size={size} strokeWidth={2} className={"ic-i " + className} aria-hidden="true" {...rest} />;
}

/** Filled star rating, e.g. <Stars n={4} /> */
export function Stars({ n, size = 14 }: { n: number; size?: number }) {
  return (
    <span className="stars" aria-label={`${n} out of 5`}>
      {[1, 2, 3, 4, 5].slice(0, Math.max(0, Math.min(5, Math.round(n)))).map((i) => <Star key={i} size={size} fill="currentColor" strokeWidth={1.5} />)}
    </span>
  );
}
