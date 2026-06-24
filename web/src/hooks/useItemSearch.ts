import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type ItemSearchResult } from "../lib/api";

const DEBOUNCE_MS = 150;
const MIN_CHARS = 2;

/** Debounced catalog search shared by the command palette, Markets, and the journal form.
    Owns the query string, its debounced value, and the (cached) results. `enabled` lets a
    caller pause fetching while a popover is closed. */
export function useItemSearch(enabled = true): {
  query: string;
  setQuery: (v: string) => void;
  debounced: string;
  results: ItemSearchResult[];
  isPending: boolean;
} {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query]);

  const q = useQuery({
    queryKey: ["item-search", debounced],
    queryFn: () => api.search(debounced),
    enabled: enabled && debounced.length >= MIN_CHARS,
  });

  return {
    query,
    setQuery,
    debounced,
    results: q.data?.results ?? [],
    isPending: q.isPending,
  };
}
