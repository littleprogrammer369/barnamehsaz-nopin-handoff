import { describe, it, expect } from "vitest";
import { toAsciiDigits, toNumber, toPersianDigits } from "../src/lib/digits";

describe("digits normalization", () => {
  it("converts Persian digits to ASCII", () => {
    expect(toAsciiDigits("۱۴۰۳")).toBe("1403");
    expect(toAsciiDigits("۰۱۲۳۴۵۶۷۸۹")).toBe("0123456789");
  });

  it("converts Arabic-Indic digits to ASCII", () => {
    expect(toAsciiDigits("١٢٣")).toBe("123");
  });

  it("leaves ASCII digits untouched", () => {
    expect(toAsciiDigits("12:30")).toBe("12:30");
  });

  it("toNumber parses mixed Persian digits", () => {
    expect(toNumber("۴۵")).toBe(45);
    expect(toNumber("١٢")).toBe(12);
    expect(toNumber(null)).toBe(0);
    expect(toNumber(7)).toBe(7);
  });

  it("toPersianDigits converts ASCII to Persian (display)", () => {
    expect(toPersianDigits("1403")).toBe("۱۴۰۳");
    expect(toPersianDigits(0)).toBe("۰");
  });
});
