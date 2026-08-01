"use client";

import {
  Activity,
  ChevronDown,
  ChevronRight,
  CircleUser,
  HeartPulse,
  LayoutDashboard,
  LogOut,
  MoreHorizontal,
  Network,
  ScrollText,
  ShieldCheck,
  ShieldAlert,
  Server,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/assets", label: "Assets", icon: Server },
  { href: "/city", label: "City view", icon: Network },
  { href: "/approvals", label: "Approvals", icon: ShieldCheck },
  { href: "/risks", label: "Risks", icon: ShieldAlert },
  { href: "/simulations", label: "Simulations", icon: Activity },
];

const MORE = [
  { href: "/health", label: "System health", icon: HeartPulse },
  {
    href: "http://127.0.0.1:8000/docs",
    label: "API reference",
    icon: ScrollText,
    external: true,
  },
];

function NavLink({
  href,
  label,
  icon: Icon,
  active,
  external,
}: {
  href: string;
  label: string;
  icon: typeof Server;
  active: boolean;
  external?: boolean;
}) {
  const className = `flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] transition ${
    active
      ? "bg-[var(--ip-blue)]/12 text-[var(--ip-blue)]"
      : "text-neutral-400 hover:bg-white/5 hover:text-neutral-100"
  }`;

  if (external) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={className}>
        <Icon className="h-4 w-4 shrink-0" />
        {label}
      </a>
    );
  }
  return (
    <Link href={href} className={className}>
      <Icon className="h-4 w-4 shrink-0" />
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--ip-grey-950)]">
      <nav className="flex w-[220px] shrink-0 flex-col border-r border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)]">
        <Link href="/" className="block border-b border-[var(--ip-grey-700)] px-4 py-4">
          <div className="text-[16px] font-semibold tracking-tight text-neutral-50">
            InfraPilot
          </div>
          <div className="mt-0.5 font-mono text-[9px] tracking-[0.14em] text-[var(--ip-blue)] uppercase">
            Resilience copilot
          </div>
        </Link>

        <div className="flex-1 space-y-0.5 overflow-y-auto p-2.5">
          {NAV.map((item) => (
            <NavLink
              key={item.href}
              {...item}
              active={pathname === item.href}
            />
          ))}

          <button
            onClick={() => setMoreOpen((open) => !open)}
            className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-[13px] text-neutral-400 transition hover:bg-white/5 hover:text-neutral-100"
          >
            <MoreHorizontal className="h-4 w-4 shrink-0" />
            More
            <ChevronDown
              className={`ml-auto h-3.5 w-3.5 transition ${moreOpen ? "rotate-180" : ""}`}
            />
          </button>
          {moreOpen && (
            <div className="space-y-0.5 pl-3">
              {MORE.map((item) => (
                <NavLink key={item.href} {...item} active={pathname === item.href} />
              ))}
            </div>
          )}
        </div>

        <div className="relative border-t border-[var(--ip-grey-700)] p-2.5">
          {profileOpen && (
            <div className="absolute right-2.5 bottom-full left-2.5 mb-1.5 rounded-md border border-[var(--ip-grey-700)] bg-[var(--ip-grey-800)] p-3">
              <p className="text-[12px] font-medium text-neutral-100">Sam Okafor</p>
              <p className="mt-0.5 text-[11px] text-neutral-500">
                OT Security Operator
              </p>
              <p className="mt-2 border-t border-[var(--ip-grey-700)] pt-2 font-mono text-[10px] leading-relaxed text-neutral-500">
                Single demo workspace — this build ships no authentication, so
                the identity above is illustrative.
              </p>
            </div>
          )}

          <button
            onClick={() => setProfileOpen((open) => !open)}
            className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-[13px] text-neutral-400 transition hover:bg-white/5 hover:text-neutral-100"
          >
            <CircleUser className="h-4 w-4 shrink-0" />
            Profile
          </button>

          <button
            disabled
            title="No authentication in this build — single demo workspace"
            className="flex w-full cursor-not-allowed items-center gap-2.5 rounded-md px-3 py-2 text-[13px] text-neutral-600"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            Sign out
          </button>
        </div>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">{children}</div>
    </div>
  );
}

/** Standard page chrome for every non-graph route. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex shrink-0 items-center justify-between border-b border-[var(--ip-grey-700)] px-6 py-3.5">
      <div>
        <h1 className="text-[17px] font-semibold tracking-tight text-neutral-50">
          {title}
        </h1>
        {subtitle && <p className="mt-0.5 text-[12px] text-neutral-500">{subtitle}</p>}
      </div>
      {actions}
    </header>
  );
}

/** Section chrome. Titles are deliberately larger and bolder than the body. */
export function Card({
  title,
  hint,
  href,
  children,
  className = "",
}: {
  title: string;
  hint?: string;
  href?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-lg border border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)] p-4 ${className}`}
    >
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-[15px] font-semibold tracking-tight text-neutral-50">
          {title}
        </h2>
        {href ? (
          <Link
            href={href}
            className="flex shrink-0 items-center gap-0.5 font-mono text-[10px] text-neutral-500 transition hover:text-[var(--ip-blue)]"
          >
            {hint ?? "View all"}
            <ChevronRight className="h-3 w-3" />
          </Link>
        ) : (
          hint && (
            <span className="shrink-0 font-mono text-[10px] text-neutral-600">
              {hint}
            </span>
          )
        )}
      </div>
      {children}
    </section>
  );
}

export function CityViewButton() {
  return (
    <Link
      href="/city"
      data-testid="city-view-button"
      className="flex items-center gap-1.5 rounded-md bg-[var(--ip-blue)] px-3.5 py-2 text-[12.5px] font-medium text-white transition hover:bg-[var(--ip-blue-dark)]"
    >
      <Network className="h-3.5 w-3.5" />
      City view
    </Link>
  );
}
