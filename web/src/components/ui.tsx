import { useId, type CSSProperties, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, Download, Star } from "lucide-react";
import type { UseQueryResult } from "@tanstack/react-query";
import { thumbUrl } from "../lib/api";
import { useWatchlist, watchlist } from "../lib/watchlist";
import { usePagination } from "../hooks/usePagination";
import { downloadCsv } from "../lib/csv";

/* ── Filters ──────────────────────────────────────────────────────────────────
   Small pill toggle for segmented filters, shared across views. */
export function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
        active ? "bg-gold/15 text-gold" : "text-ink-500 hover:bg-void-800 hover:text-ink-200"
      }`}
    >
      {children}
    </button>
  );
}

/** Compact inline filter text box (e.g. filter a loaded table by name). */
export function FilterInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      spellCheck={false}
      placeholder={placeholder}
      className="w-44 rounded-md border border-void-700 bg-void-850/70 px-2.5 py-1 text-xs text-ink-100 outline-none transition-colors placeholder:text-ink-700 focus:border-gold"
    />
  );
}

export function Pager({
  page,
  totalPages,
  total,
  start,
  pageSize,
  onPage,
}: {
  page: number;
  totalPages: number;
  total: number;
  start: number;
  pageSize: number;
  onPage: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  const from = total === 0 ? 0 : start + 1;
  const to = Math.min(start + pageSize, total);
  const btn =
    "grid h-7 w-7 place-items-center rounded-md text-ink-400 transition-colors hover:bg-void-800 hover:text-ink-100 disabled:cursor-default disabled:opacity-30 disabled:hover:bg-transparent";
  return (
    <div className="mt-3 flex items-center justify-between px-1 text-xs text-ink-600">
      <span className="nums">
        {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-1.5">
        <button className={btn} onClick={() => onPage(page - 1)} disabled={page <= 0} aria-label="Previous page">
          <ChevronLeft size={15} />
        </button>
        <span className="nums px-1 text-ink-400">
          {page + 1} / {totalPages}
        </span>
        <button
          className={btn}
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages - 1}
          aria-label="Next page"
        >
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
  );
}

/* ── Sparkline ──────────────────────────────────────────────────────────────
   Tiny trend line + area fill, auto-colored up/down unless an accent is given. */
export function Sparkline({
  data,
  width = 96,
  height = 28,
  accent,
}: {
  data: number[] | null | undefined;
  width?: number;
  height?: number;
  accent?: string;
}) {
  const id = useId();
  if (!data || data.length < 2) return <span className="text-ink-700">—</span>;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const x = (i: number) => (i / (data.length - 1)) * width;
  const y = (v: number) => height - 3 - ((v - min) / range) * (height - 6);
  const line = data.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const up = data[data.length - 1] >= data[0];
  const color = accent ?? (up ? "var(--color-up)" : "var(--color-down)");
  return (
    <svg width={width} height={height} className="block overflow-visible">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${line} L ${width} ${height} L 0 ${height} Z`} fill={`url(#${id})`} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={x(data.length - 1)} cy={y(data[data.length - 1])} r="1.8" fill={color} />
    </svg>
  );
}

/* ── Meter ── horizontal proportion bar, used for scores / discounts. */
export function Meter({
  value,
  color = "var(--color-gold)",
}: {
  value: number; // 0..1
  color?: string;
}) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-void-800">
      <div
        className="h-full rounded-full transition-[width] duration-500 ease-out"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  );
}

/* ── Pill ── small status tag. */
export type Tone = "neutral" | "up" | "down" | "gold" | "cyan" | "amber" | "violet";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "text-ink-400 bg-void-800",
  up: "text-up bg-up/10",
  down: "text-down bg-down/10",
  gold: "text-gold bg-gold/10",
  cyan: "text-cyan bg-cyan/10",
  amber: "text-amber bg-amber/10",
  violet: "text-violet bg-violet/10",
};

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${TONE_CLASS[tone]}`}
    >
      {children}
    </span>
  );
}

/** Square item thumbnail with a subtle surface; falls back to a placeholder tile. */
export function Thumb({ thumb, size = 30 }: { thumb?: string | null; size?: number }) {
  const url = thumbUrl(thumb);
  return (
    <span
      className="grid shrink-0 place-items-center overflow-hidden rounded-md border border-void-800 bg-void-850"
      style={{ width: size, height: size }}
    >
      {url ? (
        <img src={url} alt="" loading="lazy" width={size} height={size} className="object-contain" />
      ) : (
        <span className="h-1.5 w-1.5 rounded-full bg-void-700" />
      )}
    </span>
  );
}

/** Human name on top, codename/slug small underneath, with an optional thumbnail at left. */
export function ItemName({
  name,
  slug,
  thumb,
}: {
  name?: string | null;
  slug: string;
  thumb?: string | null;
}) {
  const text = (
    <div className="min-w-0 leading-tight">
      <div className="truncate font-medium text-ink-100">{name ?? slug}</div>
      {name && <div className="nums text-[11px] text-ink-700">{slug}</div>}
    </div>
  );
  if (thumb === undefined) return text;
  return (
    <div className="flex items-center gap-2.5">
      <Thumb thumb={thumb} />
      {text}
    </div>
  );
}

/** Pin/unpin an item to the watchlist. Reactive, reflects the shared store everywhere. */
export function StarButton({ slug, size = 15 }: { slug: string; size?: number }) {
  const watched = useWatchlist().includes(slug);
  return (
    <button
      onClick={(e) => {
        e.stopPropagation(); // don't trigger a row's onClick when starring
        watchlist.toggle(slug);
      }}
      aria-label={watched ? "Remove from watchlist" : "Add to watchlist"}
      aria-pressed={watched}
      title={watched ? "Unpin" : "Pin to watchlist"}
      className={`grid place-items-center rounded p-1 transition-colors ${
        watched ? "text-gold hover:text-gold-dim" : "text-ink-700 hover:text-ink-300"
      }`}
    >
      <Star size={size} fill={watched ? "currentColor" : "none"} strokeWidth={2} />
    </button>
  );
}

export function Delta({ value }: { value: number }) {
  const cls = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-ink-400";
  return <span className={cls}>{value > 0 ? "▲" : value < 0 ? "▼" : "•"}</span>;
}

/* ── Panel ── titled region on a depth surface. */
export function Panel({
  title,
  caption,
  accent = "var(--color-gold)",
  actions,
  bare = false,
  children,
}: {
  title?: string;
  caption?: string;
  accent?: string;
  actions?: ReactNode;
  bare?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="mb-7">
      {title && (
        <header className="mb-3 flex items-baseline justify-between gap-4">
          <div className="flex items-baseline gap-2.5">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: accent }} />
            <h2 className="display text-base font-semibold text-ink-50">{title}</h2>
            {caption && <span className="text-xs text-ink-600">{caption}</span>}
          </div>
          {actions}
        </header>
      )}
      <div className={bare ? "" : "surface p-1"}>{children}</div>
    </section>
  );
}

/* ── Table ────────────────────────────────────────────────────────────────── */
export interface Column<T> {
  key: string;
  header: string;
  align?: "left" | "right";
  render: (row: T) => ReactNode;
  width?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  selectedKey,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  selectedKey?: string;
}) {
  return (
    <div className="overflow-x-auto rounded-[0.6rem]">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                style={{ width: c.width }}
                className={`sticky top-0 z-10 bg-void-850/80 px-3.5 py-2.5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-ink-600 backdrop-blur-sm ${
                  c.align === "right" ? "text-right" : "text-left"
                }`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const key = rowKey(row);
            const selected = key === selectedKey;
            return (
              <tr
                key={key}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`row-in border-t border-void-800/70 transition-colors duration-200 ${
                  onRowClick ? "cursor-pointer" : ""
                } ${selected ? "bg-gold/10" : "hover:bg-void-800/50"}`}
                style={{ "--i": i } as CSSProperties}
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`px-3.5 py-2.5 align-middle ${
                      c.align === "right" ? "text-right nums" : "text-left"
                    }`}
                  >
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** DataTable + client-side paging in one. Replaces the repeated
    `usePagination → <DataTable/> + <Pager/>` wrapper every view used to hand-roll. For the
    stagger-replay-on-filter-change cases, pass `key={filter}` so it remounts and re-fires
    the row-entrance animation. */
export function PaginatedTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  pageSize = 15,
  exportName,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  pageSize?: number;
  /** When set, show a "CSV" button that exports the full (unpaginated) row set. */
  exportName?: string;
}) {
  const pg = usePagination(rows, pageSize);
  return (
    <>
      {exportName && rows.length > 0 && (
        <div className="mb-1.5 flex justify-end">
          <button
            onClick={() => downloadCsv(exportName, rows as Record<string, unknown>[])}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] text-ink-500 transition-colors hover:bg-void-800 hover:text-ink-100"
            title={`Export all ${rows.length} rows as CSV`}
          >
            <Download size={13} /> CSV
          </button>
        </div>
      )}
      <DataTable columns={columns} rows={pg.pageItems} rowKey={rowKey} onRowClick={onRowClick} />
      <Pager {...pg} onPage={pg.setPage} />
    </>
  );
}

export function SkeletonRows({ rows = 7, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="surface overflow-hidden p-1">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4 border-t border-void-800/70 px-3.5 py-3 first:border-t-0">
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={c}
              className="h-3.5 flex-1 animate-pulse rounded bg-void-800"
              style={{ animationDelay: `${(r * cols + c) * 35}ms` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function AsyncBlock<T>({
  query,
  empty,
  emptyNode,
  children,
  skeletonCols,
}: {
  query: UseQueryResult<T>;
  empty?: (data: T) => boolean;
  emptyNode?: ReactNode;
  children: (data: T) => ReactNode;
  skeletonCols?: number;
}) {
  if (query.isPending) return <SkeletonRows cols={skeletonCols} />;
  if (query.isError) {
    return (
      <div className="surface px-5 py-4 text-sm text-ink-400">
        <span className="text-down">Can't reach the API.</span> Start it with{" "}
        <code className="nums text-ink-100">voidbroker serve</code>.
        <div className="mt-1 text-xs text-ink-700">{String(query.error)}</div>
      </div>
    );
  }
  if (empty?.(query.data)) {
    return (
      emptyNode ?? (
        <div className="surface px-5 py-8 text-center text-sm text-ink-400">Nothing here yet.</div>
      )
    );
  }
  return <>{children(query.data)}</>;
}
