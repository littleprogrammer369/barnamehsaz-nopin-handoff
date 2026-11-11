/**
 * Persian/Arabic digit ↔ ASCII normalization (04 «رقم‌های فارسی/عربی را…
 * normalize to ASCII before sending to the API»).
 *
 * `toAsciiDigits`: used when building API request bodies (expected_enrollment,
 * weekday, hhmm, cohort entry_year, …).
 * `toPersianDigits`: used for display strings that must stay in Persian.
 */

const PERSIAN_MAP: Record<string, string> = {
  "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
  "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
};
const ARABIC_MAP: Record<string, string> = {
  "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
  "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
};
const ASCI_TO_PERSIAN: Record<string, string> = {
  "0": "۰", "1": "۱", "2": "۲", "3": "۳", "4": "۴",
  "5": "۵", "6": "۶", "7": "۷", "8": "۸", "9": "۹",
};

/** Convert any Persian/Arabic digits in `input` to ASCII digits. */
export function toAsciiDigits(input: string | number | null | undefined): string {
  if (input == null) return "";
  const s = String(input);
  return s
    .replace(/[۰-۹]/g, (ch) => PERSIAN_MAP[ch] ?? ch)
    .replace(/[٠-٩]/g, (ch) => ARABIC_MAP[ch] ?? ch);
}

/** Parse a possibly-Persian/Arabic-digit number into a JS number. */
export function toNumber(input: string | number | null | undefined): number {
  if (input == null) return 0;
  if (typeof input === "number") return input;
  const n = Number(toAsciiDigits(input));
  return Number.isNaN(n) ? 0 : n;
}

/** Convert ASCII digits in `input` to Persian (display) digits. */
export function toPersianDigits(input: string | number | null | undefined): string {
  if (input == null) return "";
  return String(input).replace(/[0-9]/g, (ch) => ASCI_TO_PERSIAN[ch] ?? ch);
}

/** Human-friendly number display: Persian digits, thousand separators. */
export function formatNumber(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  const localized = new Intl.NumberFormat("fa-IR").format(n);
  return localized;
}
