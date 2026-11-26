/**
 * Integer minor-unit currency formatting & parsing utilities (zero floating-point drift).
 */

const ZERO_DECIMAL_CURRENCIES = new Set(["JPY"]);

export function currencyExponent(currencyCode: string): number {
  return ZERO_DECIMAL_CURRENCIES.has(currencyCode.toUpperCase()) ? 0 : 2;
}

export function formatMinorUnits(
  minorUnits: number,
  currencyCode = "INR",
  locale?: string,
): string {
  const code = currencyCode.toUpperCase();
  const exp = currencyExponent(code);
  const major = exp === 0 ? minorUnits : minorUnits / 100;
  const resolvedLocale = locale || (code === "INR" ? "en-IN" : "en-US");
  try {
    return new Intl.NumberFormat(resolvedLocale, {
      style: "currency",
      currency: code,
      minimumFractionDigits: exp === 0 ? 0 : minorUnits % 100 === 0 ? 0 : 2,
      maximumFractionDigits: exp,
    }).format(major);
  } catch {
    return `${code} ${major.toFixed(exp)}`;
  }
}

export function minorUnitsToInputString(minorUnits: number, currencyCode = "INR"): string {
  const exp = currencyExponent(currencyCode);
  if (exp === 0) return String(minorUnits);
  const whole = Math.floor(minorUnits / 100);
  const frac = minorUnits % 100;
  return `${whole}.${String(frac).padStart(2, "0")}`;
}

export function parseDisplayToMinorUnits(raw: string, currencyCode = "INR"): number | null {
  const cleaned = raw.trim();
  if (!cleaned) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const exp = currencyExponent(currencyCode);
  if (exp === 0) {
    if (cleaned.includes(".")) return null;
    const val = Number.parseInt(cleaned, 10);
    return Number.isSafeInteger(val) && val >= 0 && val <= 100_000_000 ? val : null;
  }
  const [wholeStr, fracStr = ""] = cleaned.split(".");
  const whole = Number.parseInt(wholeStr, 10);
  const frac = Number.parseInt(fracStr.padEnd(2, "0"), 10);
  const minor = whole * 100 + frac;
  return Number.isSafeInteger(minor) && minor >= 0 && minor <= 100_000_000 ? minor : null;
}
