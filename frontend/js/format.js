// =========================================================================
// format.js · Plata y fechas en formato uruguayo.
// Recordá: la API trabaja en CENTÉSIMOS (enteros). Acá convertimos.
// =========================================================================

const uyu = new Intl.NumberFormat("es-UY", { style: "currency", currency: "UYU", maximumFractionDigits: 0 });
const uyuCents = new Intl.NumberFormat("es-UY", { style: "currency", currency: "UYU", minimumFractionDigits: 2 });
const usd = new Intl.NumberFormat("es-UY", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

/** 150050 -> "$ 1.501" (sin decimales, para números grandes del dashboard) */
export const money = (cents) => uyu.format(Math.round(cents / 100));

/** 150050 -> "$ 1.500,50" (con decimales, para listas y detalles) */
export const moneyExact = (cents, currency = "UYU") =>
  (currency === "USD" ? usd : uyuCents).format(cents / 100);

/**
 * Lo que el usuario escribe -> centésimos.
 * Acepta formatos uruguayos: "1.500,50", "1500,5", "1500.50", "1.500", "60".
 * Devuelve null si no es un número válido.
 */
export function parseMoney(text) {
  let s = String(text).replace(/[^\d.,-]/g, "");  // saca "$", espacios, letras
  if (!s) return null;
  if (s.includes(",")) {
    s = s.replace(/\./g, "").replace(",", ".");  // "1.500,50" -> "1500.50"
  } else if (/^\d{1,3}(\.\d{3})+$/.test(s)) {
    s = s.replace(/\./g, "");                    // "1.500" -> "1500" (miles)
  }
  const value = Number(s);
  return Number.isFinite(value) && value > 0 ? Math.round(value * 100) : null;
}

/** centésimos -> texto para un input ("150050" -> "1500,50") */
export const centsToInput = (cents) =>
  (cents / 100).toLocaleString("es-UY", { maximumFractionDigits: 2, useGrouping: false });

// --- Fechas ---
// Las fechas de la API vienen como "2026-11-02". Las armamos en hora local
// (new Date("2026-11-02") las tomaría como UTC y podría mostrar el día anterior).
export const parseDate = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };
export const toISO = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
export const todayISO = () => toISO(new Date());

const dayFmt = new Intl.DateTimeFormat("es-UY", { weekday: "long", day: "numeric", month: "long" });
const shortFmt = new Intl.DateTimeFormat("es-UY", { day: "numeric", month: "short" });
const monthFmt = new Intl.DateTimeFormat("es-UY", { month: "long", year: "numeric" });

const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);

/** "Hoy", "Ayer" o "Lunes 2 de noviembre" */
export function friendlyDay(iso) {
  const today = todayISO();
  const yesterday = toISO(new Date(Date.now() - 86400000));
  if (iso === today) return "Hoy";
  if (iso === yesterday) return "Ayer";
  return capitalize(dayFmt.format(parseDate(iso)));
}
export const shortDate = (iso) => shortFmt.format(parseDate(iso));

/** Rango corto: "1–7 nov." (o "29 nov. – 2 dic." si cruza de mes) */
export function shortRange(fromISO, toISO_) {
  const a = parseDate(fromISO);
  const b = parseDate(toISO_);
  if (a.getMonth() === b.getMonth()) {
    return `${a.getDate()}–${b.getDate()} ${shortFmt.format(b).replace(/^\d+\s/, "")}`;
  }
  return `${shortDate(fromISO)} – ${shortDate(toISO_)}`;
}
export const monthLabel = (year, month) => capitalize(monthFmt.format(new Date(year, month - 1, 1)));
export const longToday = () => capitalize(dayFmt.format(new Date()));
