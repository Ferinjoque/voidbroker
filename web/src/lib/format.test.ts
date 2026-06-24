import { describe, expect, it } from "vitest";
import { countdown, flip, pct, plat, signed } from "./format";

describe("plat", () => {
  it("rounds small values and compacts thousands", () => {
    expect(plat(87)).toBe("87");
    expect(plat(1200)).toBe("1.2k");
    expect(plat(12900)).toBe("12.9k");
    expect(plat(3000)).toBe("3k");
    expect(plat(null)).toBe("—");
  });
});

describe("pct", () => {
  it("renders a fraction as whole percent", () => {
    expect(pct(0.49)).toBe("49%");
    expect(pct(1)).toBe("100%");
    expect(pct(undefined)).toBe("—");
  });
});

describe("signed", () => {
  it("uses explicit sign glyphs", () => {
    expect(signed(0.2)).toBe("+0.20");
    expect(signed(-0.2)).toBe("−0.20");
    expect(signed(0)).toBe("0.00");
  });
});

describe("countdown", () => {
  it("scales unit to magnitude", () => {
    expect(countdown(0.5)).toBe("30m");
    expect(countdown(5)).toBe("5h");
    expect(countdown(50)).toBe("2d 2h");
  });
});

describe("flip", () => {
  it("switches to hours under a day", () => {
    expect(flip(0.25)).toBe("6h");
    expect(flip(2.3)).toBe("2.3d");
  });
});
