import type { ReactNode } from "react";

import type { PaceStatus } from "../api/types";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 ${className}`}>
      {children}
    </section>
  );
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-500">
      {children}
    </h2>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p
      role="alert"
      className="rounded-lg border border-red-900/50 bg-red-950/40 px-3 py-2 text-sm text-red-300"
    >
      {children}
    </p>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-zinc-500" role="status">
      <span className="size-3.5 animate-spin rounded-full border-2 border-zinc-700 border-t-zinc-300" />
      {label}
    </div>
  );
}

const PACE_STYLES: Record<PaceStatus, { label: string; className: string }> = {
  ahead: { label: "ahead", className: "bg-sky-500/10 text-sky-300 border-sky-500/25" },
  on_track: {
    label: "on pace",
    className: "bg-emerald-500/10 text-emerald-300 border-emerald-500/25",
  },
  behind: { label: "behind", className: "bg-amber-500/10 text-amber-300 border-amber-500/25" },
};

export function PaceBadge({ status }: { status: PaceStatus }) {
  const style = PACE_STYLES[status];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${style.className}`}
    >
      {style.label}
    </span>
  );
}

export function ProgressBar({ percent }: { percent: number | null }) {
  const width = percent === null ? 0 : Math.min(100, Math.max(0, percent));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
      <div
        className="h-full rounded-full bg-emerald-500/80 transition-[width] duration-500"
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger";
};

export function Button({ variant = "primary", className = "", ...props }: ButtonProps) {
  const variants = {
    primary:
      "bg-emerald-600 text-white hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-500",
    ghost:
      "border border-zinc-700 text-zinc-300 hover:border-zinc-500 hover:text-zinc-100 disabled:text-zinc-600",
    danger: "border border-red-900/60 text-red-300 hover:border-red-700 disabled:text-zinc-600",
  } as const;
  return (
    <button
      className={`rounded-xl px-4 py-2.5 text-sm font-medium transition-colors disabled:cursor-not-allowed ${variants[variant]} ${className}`}
      {...props}
    />
  );
}
