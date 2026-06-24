import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import {
  ChevronDown,
  CircleUser,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  X,
} from "lucide-react";
import { NAV, type ViewId } from "./nav";

export type { ViewId } from "./nav";

const LS_COLLAPSED = "vb_sidebar_collapsed";
const LS_REDUCE_MOTION = "vb_reduce_motion";
const LS_DENSITY = "vb_density"; // "compact" tightens table row height

const Diamond = () => (
  <span
    className="block h-4 w-4 shrink-0 rotate-45 rounded-[3px] bg-gold"
    style={{ boxShadow: "0 0 14px 1px oklch(83% 0.135 86 / 0.5)" }}
    aria-hidden
  />
);

/** A text label that collapses horizontally (fade + max-width) so nothing clips,
    used identically by the logo, nav items, and footer for one consistent motion. */
function Label({
  show,
  max = 180,
  children,
}: {
  show: boolean;
  max?: number;
  children: ReactNode;
}) {
  return (
    <span
      className="overflow-hidden whitespace-nowrap transition-all duration-300 ease-out"
      style={{ maxWidth: show ? max : 0, opacity: show ? 1 : 0, marginLeft: show ? 10 : 0 }}
    >
      {children}
    </span>
  );
}

function Popover({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div className="fade-in absolute bottom-full left-2 z-50 mb-2 w-56 rounded-lg border border-void-700 bg-void-850 p-3 shadow-2xl">
        {children}
      </div>
    </>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={`relative h-5 w-9 rounded-full transition-colors duration-200 ${
        on ? "bg-gold" : "bg-void-700"
      }`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-void-950 transition-transform duration-200 ${
          on ? "translate-x-4" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

export function Sidebar({ view, onSelect }: { view: ViewId; onSelect: (id: ViewId) => void }) {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(LS_COLLAPSED) === "1");
  const [closedGroups, setClosedGroups] = useState<Set<string>>(new Set());
  const [popover, setPopover] = useState<"account" | "settings" | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(
    () => localStorage.getItem(LS_REDUCE_MOTION) === "1",
  );
  const [compact, setCompact] = useState(() => localStorage.getItem(LS_DENSITY) === "compact");

  // Persist only — collapsing also closes the popover, but that's done in `setCollapse`
  // (an event handler) rather than here, so this effect never calls setState.
  useEffect(() => {
    localStorage.setItem(LS_COLLAPSED, collapsed ? "1" : "0");
  }, [collapsed]);
  useEffect(() => {
    document.documentElement.dataset.reduceMotion = reduceMotion ? "1" : "0";
    localStorage.setItem(LS_REDUCE_MOTION, reduceMotion ? "1" : "0");
  }, [reduceMotion]);
  useEffect(() => {
    document.documentElement.dataset.density = compact ? "compact" : "comfortable";
    localStorage.setItem(LS_DENSITY, compact ? "compact" : "comfortable");
  }, [compact]);

  const setCollapse = (next: boolean) => {
    setCollapsed(next);
    if (next) setPopover(null);
  };
  // On mobile the rail is an overlay; picking a destination should dismiss it.
  const select = (id: ViewId) => {
    onSelect(id);
    setMobileOpen(false);
  };

  const groups = [...new Set(NAV.map((n) => n.group))];
  const toggleGroup = (g: string) =>
    setClosedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(g)) next.delete(g);
      else next.add(g);
      return next;
    });

  // Keep justify-content fixed (flex-start) and animate the left padding instead.
  // Changing justify-content is instant and snaps the icon to center before the width
  // has moved; animating padding slides it smoothly. 17px centers a 17px icon in the
  // collapsed 52px content box.
  const rowStyle: CSSProperties = {
    justifyContent: "flex-start",
    paddingLeft: collapsed ? 17 : 10,
    paddingRight: collapsed ? 17 : 10,
  };

  // Subtitle row: text fades fast (so it never clips), but the row HEIGHT only
  // collapses after the width has finished (delay on close) so icons don't jump.
  const subtitleRow: CSSProperties = {
    gridTemplateRows: collapsed ? "0fr" : "1fr",
    transition: "grid-template-rows 220ms ease",
    transitionDelay: collapsed ? "240ms" : "0ms",
  };
  const subtitleText: CSSProperties = {
    opacity: collapsed ? 0 : 1,
    transition: "opacity 150ms ease",
    transitionDelay: collapsed ? "0ms" : "200ms",
  };

  return (
    <>
      {/* Mobile-only: a floating button to reveal the rail, and a backdrop to dismiss it.
          Hidden from md up, where the rail is a permanent sticky column. */}
      <button
        onClick={() => setMobileOpen(true)}
        aria-label="Open navigation"
        className="fixed left-3 top-3 z-[55] grid h-10 w-10 place-items-center rounded-lg border border-void-800/70 bg-void-900/80 text-ink-200 backdrop-blur-sm transition-colors hover:text-gold md:hidden"
      >
        <Menu size={18} />
      </button>
      {mobileOpen && (
        <div
          className="fade-in fixed inset-0 z-40 bg-void-950/70 backdrop-blur-[2px] md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <nav
        className={`fixed inset-y-0 left-0 z-50 flex h-screen flex-col border-r border-void-800/70 bg-void-900/95 py-4 backdrop-blur-sm transition-[transform,width,padding] duration-300 ease-out md:sticky md:top-0 md:z-auto md:shrink-0 md:translate-x-0 md:bg-void-900/40 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } ${collapsed ? "w-[68px] px-2" : "w-60 px-3.5"}`}
      >
        {/* Mobile-only close affordance inside the drawer. */}
        <button
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
          className="absolute right-2 top-3 grid h-8 w-8 place-items-center rounded-md text-ink-500 hover:text-ink-100 md:hidden"
        >
          <X size={16} />
        </button>
      {/* Header: single structure. Left padding animates (no justify flip) so the
          diamond slides to the rail center as the name + toggle collapse. Open padding
          matches the nav rows below (10) so the logo's left edge aligns with the icons. */}
      <div
        className="group relative mb-7 flex h-7 shrink-0 items-center transition-[padding] duration-300 ease-out"
        style={{ paddingLeft: collapsed ? 17 : 10 }}
      >
        <span className={collapsed ? "transition-opacity duration-200 group-hover:opacity-0" : ""}>
          <Diamond />
        </span>
        <span
          className="display overflow-hidden whitespace-nowrap text-[17px] font-semibold tracking-tight text-ink-50 transition-all duration-300 ease-out"
          style={{ maxWidth: collapsed ? 0 : 160, opacity: collapsed ? 0 : 1, marginLeft: collapsed ? 0 : 10 }}
        >
          voidbroker
        </span>
        <button
          onClick={() => setCollapse(true)}
          aria-label="Collapse sidebar"
          title="Collapse"
          tabIndex={collapsed ? -1 : 0}
          className="grid h-7 place-items-center overflow-hidden rounded-md text-ink-600 transition-all duration-300 hover:bg-void-800 hover:text-ink-100"
          style={{ marginLeft: collapsed ? 0 : "auto", maxWidth: collapsed ? 0 : 28, opacity: collapsed ? 0 : 1 }}
        >
          <PanelLeftClose size={16} />
        </button>
        {collapsed && (
          <button
            onClick={() => setCollapse(false)}
            aria-label="Expand sidebar"
            title="Expand"
            className="absolute inset-0 grid place-items-center text-ink-400 opacity-0 transition-opacity duration-200 hover:text-ink-100 group-hover:opacity-100"
          >
            <PanelLeftOpen size={18} />
          </button>
        )}
      </div>

      {/* Nav groups — flex-1 so it fills the pinned column and scrolls internally when
          there are more items than fit, keeping the footer always visible (scalable). */}
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overflow-x-hidden">
        {groups.map((g) => {
          const closed = closedGroups.has(g);
          const showItems = collapsed || !closed;
          return (
            <div key={g}>
              <div className="grid" style={subtitleRow}>
                <div className="overflow-hidden">
                  <button
                    onClick={() => toggleGroup(g)}
                    tabIndex={collapsed ? -1 : 0}
                    className="group mb-1 flex w-full items-center justify-between px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-ink-700 transition-colors hover:text-ink-400"
                  >
                    <span style={subtitleText}>{g}</span>
                    <ChevronDown
                      size={13}
                      className={`transition-all duration-200 ${
                        closed ? "-rotate-90 opacity-60" : "opacity-0 group-hover:opacity-100"
                      }`}
                    />
                  </button>
                </div>
              </div>
              {showItems && (
                <ul className="flex flex-col gap-0.5">
                  {NAV.filter((n) => n.group === g).map((n) => {
                    const active = view === n.id;
                    const Ico = n.icon;
                    return (
                      <li key={n.id}>
                        <button
                          onClick={() => select(n.id)}
                          title={collapsed ? n.label : undefined}
                          style={rowStyle}
                          className={`flex w-full items-center rounded-lg py-2 text-sm transition-all duration-300 ease-out ${
                            active
                              ? "bg-void-800 font-medium text-gold"
                              : "text-ink-400 hover:bg-void-800/50 hover:text-ink-100"
                          }`}
                        >
                          <Ico size={17} strokeWidth={active ? 2.4 : 2} className="shrink-0" />
                          <Label show={!collapsed}>{n.label}</Label>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer: settings above account, stacked the same in both states so it animates
          consistently (label collapses, icon centers) instead of reflowing. */}
      <div className="relative flex shrink-0 flex-col gap-0.5 pt-5">
        <button
          onClick={() => setPopover(popover === "settings" ? null : "settings")}
          title="Settings"
          aria-label="Settings"
          style={rowStyle}
          className="flex items-center rounded-lg py-2 text-sm text-ink-400 transition-all duration-300 ease-out hover:bg-void-800/50 hover:text-ink-100"
        >
          <Settings size={17} className="shrink-0" />
          <Label show={!collapsed}>Settings</Label>
        </button>
        <button
          onClick={() => setPopover(popover === "account" ? null : "account")}
          title="Account"
          style={rowStyle}
          className="flex items-center rounded-lg py-2 text-sm text-ink-400 transition-all duration-300 ease-out hover:bg-void-800/50 hover:text-ink-100"
        >
          <CircleUser size={18} strokeWidth={2} className="shrink-0" />
          <Label show={!collapsed}>Local session</Label>
        </button>

        {popover === "account" && (
          <Popover onClose={() => setPopover(null)}>
            <div className="mb-2 text-sm font-medium text-ink-100">Local session</div>
            <dl className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <dt className="text-ink-600">Platform</dt>
                <dd className="nums text-ink-300">pc</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-600">Archive</dt>
                <dd className="nums text-ink-300">local DuckDB</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-600">Read API</dt>
                <dd className="nums text-ink-300">:8000</dd>
              </div>
            </dl>
          </Popover>
        )}
        {popover === "settings" && (
          <Popover onClose={() => setPopover(null)}>
            <div className="mb-3 text-sm font-medium text-ink-100">Settings</div>
            <label className="flex items-center justify-between gap-3 text-xs text-ink-300">
              <span>Reduce motion</span>
              <Toggle on={reduceMotion} onChange={setReduceMotion} />
            </label>
            <label className="mt-2.5 flex items-center justify-between gap-3 text-xs text-ink-300">
              <span>Compact tables</span>
              <Toggle on={compact} onChange={setCompact} />
            </label>
          </Popover>
        )}
      </div>
      </nav>
    </>
  );
}
