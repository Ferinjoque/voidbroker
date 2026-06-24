import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { useItemSearch } from "../hooks/useItemSearch";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { NAV, type ViewId } from "./nav";
import { Thumb } from "./ui";

type Entry =
  | { kind: "view"; id: ViewId; label: string; group: string; Icon: (typeof NAV)[number]["icon"] }
  | { kind: "item"; slug: string; name: string | null; thumb: string | null };

/** Global Cmd/Ctrl+K palette. Jump to any view by name or search the whole item catalog,
    keyboard-first. Views match on a single character; items search at 2+. */
export function CommandPalette({
  onOpenItem,
  onNavigate,
}: {
  onOpenItem: (slug: string, name?: string | null, thumb?: string | null) => void;
  onNavigate: (id: ViewId) => void;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const { query: q, setQuery: setQ, debounced, results, isPending } = useItemSearch(open);

  useFocusTrap(dialogRef, open);

  const term = debounced.toLowerCase();
  const viewEntries: Entry[] =
    term.length >= 1
      ? NAV.filter((n) => n.label.toLowerCase().includes(term) || n.group.toLowerCase().includes(term)).map(
          (n) => ({ kind: "view", id: n.id, label: n.label, group: n.group, Icon: n.icon }),
        )
      : [];
  const itemEntries: Entry[] = results.map((r) => ({
    kind: "item",
    slug: r.slug,
    name: r.name,
    thumb: r.thumb,
  }));
  const entries: Entry[] = [...viewEntries, ...itemEntries];

  // Cmd/Ctrl+K toggles; Esc closes. Resetting query/active here (an event handler) rather
  // than in an effect keeps the open-state side effects out of render.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setQ("");
        setActive(0);
        setOpen((v) => !v);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setQ]);

  // Focus the input when the palette opens, a DOM side effect, no setState.
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    return () => clearTimeout(t);
  }, [open]);

  const choose = (i: number) => {
    const e = entries[i];
    if (!e) return;
    if (e.kind === "view") onNavigate(e.id);
    else onOpenItem(e.slug, e.name, e.thumb);
    setOpen(false);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex justify-center pt-[12vh]">
      <div className="fade-in absolute inset-0 bg-void-950/70 backdrop-blur-[2px]" onClick={() => setOpen(false)} />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Search items"
        className="fade-in relative h-fit w-[560px] max-w-[92vw] overflow-hidden rounded-xl border border-void-700 bg-void-900 shadow-2xl"
      >
        <div className="flex items-center gap-3 border-b border-void-800 px-4">
          <Search size={16} className="text-ink-600" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, entries.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              } else if (e.key === "Enter") {
                choose(active);
              }
            }}
            spellCheck={false}
            placeholder="Jump to a view or search any item…"
            className="w-full bg-transparent py-3.5 text-sm text-ink-100 outline-none placeholder:text-ink-700"
          />
          <kbd className="nums rounded border border-void-700 px-1.5 py-0.5 text-[10px] text-ink-600">esc</kbd>
        </div>
        <ul className="max-h-[50vh] overflow-auto p-1.5">
          {debounced.length < 1 && (
            <li className="px-3 py-6 text-center text-xs text-ink-700">
              Type a view name to jump, or 2+ letters to search the catalog.
            </li>
          )}
          {entries.length === 0 && debounced.length >= 2 && !isPending && (
            <li className="px-3 py-6 text-center text-xs text-ink-700">No matches.</li>
          )}
          {entries.map((e, i) =>
            e.kind === "view" ? (
              <li key={`view:${e.id}`}>
                <button
                  onMouseEnter={() => setActive(i)}
                  onClick={() => choose(i)}
                  className={`flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left transition-colors ${
                    i === active ? "bg-void-800" : "hover:bg-void-800/50"
                  }`}
                >
                  <span className="grid h-[26px] w-[26px] place-items-center rounded-md border border-void-800 bg-void-850 text-gold">
                    <e.Icon size={14} />
                  </span>
                  <span className="flex-1 truncate text-sm text-ink-100">{e.label}</span>
                  <span className="text-[10px] uppercase tracking-wide text-ink-700">
                    {e.group} · view
                  </span>
                </button>
              </li>
            ) : (
              <li key={`item:${e.slug}`}>
                <button
                  onMouseEnter={() => setActive(i)}
                  onClick={() => choose(i)}
                  className={`flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left transition-colors ${
                    i === active ? "bg-void-800" : "hover:bg-void-800/50"
                  }`}
                >
                  <Thumb thumb={e.thumb} size={26} />
                  <span className="flex-1 truncate text-sm text-ink-100">{e.name ?? e.slug}</span>
                  <span className="nums text-[11px] text-ink-700">{e.slug}</span>
                </button>
              </li>
            ),
          )}
        </ul>
      </div>
    </div>
  );
}
