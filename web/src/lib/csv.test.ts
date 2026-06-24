import { describe, expect, it } from "vitest";
import { toCsv } from "./csv";

describe("toCsv", () => {
  it("returns empty string for no rows", () => {
    expect(toCsv([])).toBe("");
  });

  it("emits a header from the union of scalar keys", () => {
    const csv = toCsv([{ slug: "ash", price: 12 }]);
    expect(csv).toBe("slug,price\nash,12");
  });

  it("quotes values containing commas, quotes, or newlines", () => {
    const csv = toCsv([{ note: "a,b", q: 'say "hi"' }]);
    expect(csv).toBe('note,q\n"a,b","say ""hi"""');
  });

  it("renders null/undefined as empty and joins arrays", () => {
    const csv = toCsv([{ a: null, b: undefined, c: [1, 2, 3] }]);
    expect(csv).toBe('a,b,c\n,,"1 2 3"');
  });

  it("skips nested object columns", () => {
    const csv = toCsv([{ slug: "ash", meta: { x: 1 } }]);
    expect(csv).toBe("slug\nash");
  });
});
