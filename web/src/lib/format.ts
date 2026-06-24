/** Display formatters. Kept pure and tested; they run on every table row. */

/** Platinum amounts: compact above 1k (e.g. 12,900 -> "12.9k"). */
export function plat(value: number | null | undefined): string {
  if (value == null) return "—";
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(value % 1000 === 0 ? 0 : 1)}k`;
  }
  return `${Math.round(value)}`;
}

/** A 0..1 fraction as a whole-number percent. */
export function pct(fraction: number | null | undefined): string {
  if (fraction == null) return "—";
  return `${Math.round(fraction * 100)}%`;
}

/** A 0..1 fraction as a signed percent (e.g. +12.5%, −3.0%). */
export function signedPct(fraction: number | null | undefined, digits = 1): string {
  if (fraction == null) return "—";
  const v = fraction * 100;
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

/** A signed value with explicit + / − and fixed precision. */
export function signed(value: number | null | undefined, digits = 2): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(digits)}`;
}

/** Hours as a coarse human countdown ("3d 4h", "5h", "22m"). */
export function countdown(hours: number | null | undefined): string {
  if (hours == null) return "—";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.round(hours)}h`;
  const d = Math.floor(hours / 24);
  const h = Math.round(hours % 24);
  return h ? `${d}d ${h}h` : `${d}d`;
}

/** Estimated flip time in days as a short label. */
export function flip(days: number | null | undefined): string {
  if (days == null) return "—";
  if (days < 1) return `${Math.round(days * 24)}h`;
  return `${days.toFixed(days < 10 ? 1 : 0)}d`;
}
