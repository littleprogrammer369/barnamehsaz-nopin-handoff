import { describe, it, expect } from "vitest";
import { WEEKDAYS, weekdayLabel, formatTime, formatJalaliDate } from "../src/lib/persian";

describe("persian calendar + weekday helpers", () => {
  it("exposes the 7 weekday labels starting with Shabaneh", () => {
    expect(WEEKDAYS[0]).toBe("شنبه");
    expect(WEEKDAYS[6]).toBe("جمعه");
    expect(WEEKDAYS.length).toBe(7);
  });

  it("weekdayLabel returns the right label and neutral dash for out-of-range", () => {
    expect(weekdayLabel(0)).toBe("شنبه");
    expect(weekdayLabel(6)).toBe("جمعه");
    expect(weekdayLabel(null)).toBe("—");
    expect(weekdayLabel(-1)).toBe("—");
    expect(weekdayLabel(7)).toBe("—");
    expect(weekdayLabel(undefined)).toBe("—");
  });

  it("formatTime normalizes Persian-digit HH:MM to ASCII", () => {
    expect(formatTime("۰۸:۳۰")).toBe("08:30");
    expect(formatTime(null)).toBe("—");
  });

  it("formatJalaliDate returns a dash for empty input", () => {
    expect(formatJalaliDate(null)).toBe("—");
    expect(formatJalaliDate("")).toBe("—");
  });
});
