/** Minimal hash-based routing — no router dependency. The active view (and the Markets
    slug) live in the URL so refresh survives, the back button works, and any screen is a
    shareable link, e.g. #view=markets&slug=ash-prime-set. */
import { NAV, type ViewId } from "../components/nav";

const VIEW_IDS = new Set<string>(NAV.map((n) => n.id));

export interface Route {
  view: ViewId;
  slug: string;
}

export function parseHash(): Route {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const view = params.get("view");
  return {
    view: view && VIEW_IDS.has(view) ? (view as ViewId) : "digest",
    slug: params.get("slug") ?? "",
  };
}

/** Write the route to the hash. `replace` avoids a history entry (use on first mount so
    the back button doesn't trap you on the initial view). */
export function writeHash(route: Route, replace = false): void {
  const params = new URLSearchParams();
  params.set("view", route.view);
  if (route.slug) params.set("slug", route.slug);
  const next = `#${params.toString()}`;
  if (next === window.location.hash) return;
  if (replace) {
    window.history.replaceState(null, "", next);
  } else {
    window.location.hash = next;
  }
}
