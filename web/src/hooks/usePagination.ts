import { useState } from "react";

/** Client-side paging for long lists. Returns the current slice plus controls state; pair
    with <Pager> or use <PaginatedTable>. `page` is clamped on read, so if the source list
    shrinks below the current page the last page is shown (no stored-state reset needed). */
export function usePagination<T>(items: T[], pageSize = 15) {
  const [page, setPage] = useState(0);
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const start = safePage * pageSize;
  const pageItems = items.slice(start, start + pageSize);
  return { page: safePage, setPage, total, totalPages, pageItems, start, pageSize };
}
