/**
 * Persian (Jalali) calendar + digit utilities.
 *
 * The backend stores ISO 8601 dates; the UI must display Jalali (04).
 * We use `Intl.DateTimeFormat` with the Persian calendar locale, which is
 * built into modern browsers/Node — no extra dependency, no CDN.
 *
 * Weekday convention (02): 0 = شنبه … 6 = جمعه.
 */

export const WEEKDAYS: string[] = [
  "شنبه",
  "یکشنبه",
  "دوشنبه",
  "سه‌شنبه",
  "چهارشنبه",
  "پنجشنبه",
  "جمعه",
];

export const WEEKDAY_ABBR: string[] = ["ش", "ی", "د", "س", "چ", "پ", "ج"];

const JALALI_LOCALE = "fa-IR-u-ca-persian";
const GREGORIAN_LOCALE = "fa-IR";

/** Format an ISO 8601 / date string as a Jalali date, e.g. `۱۴۰۳/۰۷/۱۵`. */
export function formatJalaliDate(
  iso: string | Date | null | undefined,
): string {
  if (iso == null || iso === "") return "—";
  const d = iso instanceof Date ? iso : new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  try {
    return new Intl.DateTimeFormat(JALALI_LOCALE, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(d);
  } catch {
    return d.toLocaleDateString(GREGORIAN_LOCALE);
  }
}

/** Format an ISO 8601 / date string as a Jalali date with weekday. */
export function formatJalaliDateWithWeekday(
  iso: string | Date | null | undefined,
): string {
  if (iso == null || iso === "") return "—";
  const d = iso instanceof Date ? iso : new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  try {
    return new Intl.DateTimeFormat(JALALI_LOCALE, {
      weekday: "long",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(d);
  } catch {
    return d.toLocaleDateString(GREGORIAN_LOCALE);
  }
}

/** Human Jalali date + time string, e.g. `۱۴۰۳/۰۷/۱۵، ۱۴:۳۲`. */
export function formatJalaliDateTime(
  iso: string | Date | null | undefined,
): string {
  if (iso == null || iso === "") return "—";
  const d = iso instanceof Date ? iso : new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  try {
    const date = new Intl.DateTimeFormat(JALALI_LOCALE, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(d);
    const time = new Intl.DateTimeFormat(JALALI_LOCALE, {
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
    return `${date}، ${time}`;
  } catch {
    return d.toLocaleString(GREGORIAN_LOCALE);
  }
}

/**
 * Convert a weekday index (0=شنبه … 6=جمعه) to its Persian label.
 * Returns a neutral dash for out-of-range input rather than an array hole.
 */
export function weekdayLabel(index: number | null | undefined): string {
  if (index == null || index < 0 || index > 6) return "—";
  return WEEKDAYS[index];
}

/** Convert a `HH:MM` string (possibly Persian/Arabic digits) to ASCII digits. */
export function formatTime(hhmm: string | null | undefined): string {
  if (!hhmm) return "—";
  const PERSIAN_MAP: Record<string, string> = {
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
  };
  const ARABIC_MAP: Record<string, string> = {
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
  };
  return hhmm
    .replace(/[۰-۹]/g, (ch) => PERSIAN_MAP[ch] ?? ch)
    .replace(/[٠-٩]/g, (ch) => ARABIC_MAP[ch] ?? ch);
}
