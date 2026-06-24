/** Local-first watchlist: a set of pinned item slugs persisted to localStorage and shared
    across the app via useSyncExternalStore, so a star toggled in one view updates every
    other instantly. No backend, this is the user's own private pin board. */
import { useSyncExternalStore } from "react";

const LS_KEY = "vb_watchlist";

function load(): string[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((s) => typeof s === "string") : [];
  } catch {
    return [];
  }
}

let slugs: string[] = load();
const listeners = new Set<() => void>();

function emit() {
  // Fresh array reference each change so useSyncExternalStore detects the update.
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(slugs));
  } catch {
    /* storage full / disabled, keep the in-memory copy working anyway */
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  // Reflect edits made in another tab.
  const onStorage = (e: StorageEvent) => {
    if (e.key === LS_KEY) {
      slugs = load();
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export const watchlist = {
  has: (slug: string) => slugs.includes(slug),
  toggle(slug: string) {
    slugs = slugs.includes(slug) ? slugs.filter((s) => s !== slug) : [...slugs, slug];
    emit();
  },
  remove(slug: string) {
    if (slugs.includes(slug)) {
      slugs = slugs.filter((s) => s !== slug);
      emit();
    }
  },
};

/** Reactive list of watched slugs (re-renders on any change, including other tabs). */
export function useWatchlist(): string[] {
  return useSyncExternalStore(subscribe, () => slugs);
}
