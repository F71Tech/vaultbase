// suscripciones.js · Spotify, Claude, Netflix… cuánto suman y cuándo se cobran.

import { api } from "../api.js";
import { centsToInput, money, moneyExact, parseMoney } from "../format.js";
import { SUB_FREQUENCY } from "../labels.js";
import { mountShell } from "../shell.js";
import { confirmDialog, countUp, createSheet, esc, icons, notifyDataChanged, onDataChanged, toast } from "../ui.js";

const $ = (id) => document.getElementById(id);
let subs = [];
let rate = null;

// Atajos para cargar rápido. Solo sugieren el nombre y la moneda:
// el monto lo ponés vos (los precios cambian).
const TEMPLATES = [
  ["Spotify", "USD"], ["YouTube Premium", "USD"], ["Netflix", "USD"], ["Claude", "USD"],
  ["ChatGPT", "USD"], ["Disney+", "USD"], ["Prime Video", "USD"], ["iCloud", "USD"],
  ["Google One", "USD"], ["Instagram / Meta Verified", "USD"], ["Xbox Game Pass", "USD"], ["Gimnasio", "UYU"],
];

// Color de "avatar" estable para cada nombre (siempre el mismo color para Spotify)
const AVATAR_COLORS = ["--cat-1", "--cat-2", "--cat-3", "--cat-4", "--cat-5", "--cat-6"];
const avatarColor = (name) => AVATAR_COLORS[[...name].reduce((s, c) => s + c.charCodeAt(0), 0) % AVATAR_COLORS.length];

/** Monto mensual en pesos de una suscripción (las anuales se dividen en 12). */
function monthlyUYU(s) {
  const pesos = s.currency === "USD" ? s.amount_cents * (rate ?? 0) : s.amount_cents;
  return s.frequency === "annual" ? pesos / 12 : pesos;
}

/** Próxima fecha de cobro según el día del mes (si el mes es corto, el último día). */
function nextCharge(s, from = new Date()) {
  const today = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  for (let add = 0; add < 13; add++) {
    const y = today.getFullYear();
    const m = today.getMonth() + add;
    const lastDay = new Date(y, m + 1, 0).getDate();
    const date = new Date(y, m, Math.min(s.billing_day, lastDay));
    if (date >= today) return date;
  }
  return today;
}

function daysUntil(date) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const days = Math.round((date - today) / 86400000);
  return days === 0 ? "hoy" : days === 1 ? "mañana" : `en ${days} días`;
}

function render(income) {
  const active = subs.filter((s) => s.active);
  const perMonth = active.reduce((sum, s) => sum + monthlyUYU(s), 0);
  countUp($("sum-month"), perMonth);
  countUp($("sum-year"), perMonth * 12);
  countUp($("sum-count"), active.length * 100, (v) => String(Math.round(v / 100)));
  countUp($("sum-pct"), income ? (perMonth / income) * 10000 : 0,
    (v) => `${(v / 100).toLocaleString("es-UY", { maximumFractionDigits: 1 })}%`);

  $("sub-list").innerHTML = subs.length ? subs.map((s) => `
    <div class="row" data-sub="${s.id}" style="${s.active ? "" : "opacity:.55"}">
      <span class="avatar" style="background:color-mix(in srgb, var(${avatarColor(s.name)}) 18%, transparent);color:var(${avatarColor(s.name)})">
        ${esc(s.name.charAt(0).toUpperCase())}</span>
      <span class="flex-1 min-w-0">
        <span class="block font-medium truncate">${esc(s.name)}</span>
        <span class="block muted text-xs">${SUB_FREQUENCY[s.frequency]} · día ${s.billing_day}${s.active ? "" : " · pausada"}</span>
      </span>
      <span class="text-right">
        <span class="block font-semibold">${moneyExact(s.amount_cents, s.currency)}</span>
        ${s.currency === "USD" && rate ? `<span class="block muted text-xs">≈ ${money(s.amount_cents * rate)}</span>` : ""}
      </span>
      <button class="switch" role="switch" aria-checked="${s.active}" aria-label="Activa" data-toggle="${s.id}"></button>
    </div>`).join("")
    : `<div class="text-center muted py-8"><i data-lucide="repeat" class="w-10 h-10 mx-auto mb-3 opacity-60"></i>
        <p class="mb-4">Sumá Spotify, Netflix, Claude… y mirá cuánto te cuestan por año.</p>
        <button class="btn btn-primary text-sm" data-new><i data-lucide="plus" class="w-4 h-4"></i>Agregar la primera</button></div>`;

  // Próximos cobros (30 días), ordenados por fecha
  const upcoming = active.map((s) => ({ s, date: nextCharge(s) }))
    .filter(({ date }) => date - new Date() < 31 * 86400000)
    .sort((a, b) => a.date - b.date);
  $("upcoming").innerHTML = upcoming.length ? upcoming.map(({ s, date }, i) => `
    <li class="relative pl-5 rise" style="animation-delay:${0.2 + i * 0.06}s">
      <span class="absolute -left-[7px] top-1.5 w-3 h-3 rounded-full" style="background:${i === 0 ? "var(--accent)" : "var(--primary)"}"></span>
      <div class="flex justify-between gap-2"><span class="font-medium">${esc(s.name)}</span>
        <span class="font-semibold">${moneyExact(s.amount_cents, s.currency)}</span></div>
      <div class="muted text-xs">${date.toLocaleDateString("es-UY", { weekday: "short", day: "numeric", month: "short" })} · ${daysUntil(date)}</div>
    </li>`).join("") : `<li class="pl-5 muted text-sm">Nada en los próximos 30 días.</li>`;
  icons();
}

async function load() {
  const [list, rateInfo, overview] = await Promise.all([
    api("/api/subscriptions"), api("/api/exchange-rate").catch(() => null), api("/api/finance/overview"),
  ]);
  subs = list;
  rate = rateInfo?.rate ?? null;
  if (rate) $("rate-note").textContent = `Las que cobran en dólares se convierten a $ ${rate.toLocaleString("es-UY", { minimumFractionDigits: 2 })} (BCU).`;
  render(overview.capacity.recurring_income_cents);
}

// --- Hoja: crear / editar suscripción ---
let sheet;
let editing = null;
let currency = "USD";
function openSheet(sub = null) {
  editing = sub;
  sheet ??= createSheet(`
    <form id="sub-form" class="space-y-3" novalidate>
      <div class="flex items-center justify-between">
        <h3 class="font-display text-xl font-bold" id="sf-title"></h3>
        <div class="segmented" role="group" aria-label="Moneda">
          <button type="button" data-currency="UYU">$U</button><button type="button" data-currency="USD">US$</button>
        </div>
      </div>
      <div class="flex flex-wrap gap-2" id="sf-templates">
        ${TEMPLATES.map(([n, c]) => `<button type="button" class="chip" data-template="${esc(n)}" data-cur="${c}">${esc(n)}</button>`).join("")}
      </div>
      <label class="field"><span>Nombre</span><input id="sf-name" class="input" maxlength="80" placeholder="Ej: Spotify" /></label>
      <div class="grid grid-cols-3 gap-3">
        <label class="field col-span-1"><span>Monto</span><input id="sf-amount" class="input" inputmode="decimal" placeholder="11,99" /></label>
        <label class="field"><span>Frecuencia</span><select id="sf-frequency" class="input">
          ${Object.entries(SUB_FREQUENCY).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></label>
        <label class="field"><span>Día de cobro</span><input id="sf-day" class="input" type="number" min="1" max="31" /></label>
      </div>
      <p class="form-error" id="sf-error"></p>
      <div class="flex gap-3">
        <button type="button" class="btn btn-danger" id="sf-delete"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
        <button class="btn btn-primary flex-1">Guardar</button>
      </div>
    </form>`, { label: "Suscripción" });
  const q = (s) => sheet.el.querySelector(s);
  const syncCurrency = () => sheet.el.querySelectorAll("[data-currency]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.currency === currency));
  if (!sheet.ready) {
    sheet.ready = true;
    sheet.el.addEventListener("click", (e) => {
      const cur = e.target.closest("[data-currency]");
      const tpl = e.target.closest("[data-template]");
      if (cur) { currency = cur.dataset.currency; syncCurrency(); }
      if (tpl) { q("#sf-name").value = tpl.dataset.template; currency = tpl.dataset.cur; syncCurrency(); q("#sf-amount").focus(); }
    });
    q("#sub-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = q("#sf-name").value.trim();
      const amount = parseMoney(q("#sf-amount").value);
      const day = Number(q("#sf-day").value);
      if (!name) return (q("#sf-error").textContent = "Poné el nombre (o tocá un atajo).");
      if (!amount) return (q("#sf-error").textContent = "Escribí el monto que te cobran.");
      if (!(day >= 1 && day <= 31)) return (q("#sf-error").textContent = "El día de cobro va de 1 a 31.");
      const body = { name, amount_cents: amount, currency, frequency: q("#sf-frequency").value, billing_day: day };
      try {
        await api(editing ? `/api/subscriptions/${editing.id}` : "/api/subscriptions", { method: editing ? "PATCH" : "POST", body });
        toast(editing ? "Suscripción actualizada" : "Suscripción agregada");
        sheet.close();
        notifyDataChanged();
      } catch (err) { q("#sf-error").textContent = err.message; }
    });
    q("#sf-delete").addEventListener("click", async () => {
      if (!(await confirmDialog(`¿Borrar ${editing.name}?`))) return;
      await api(`/api/subscriptions/${editing.id}`, { method: "DELETE" });
      toast("Suscripción borrada");
      sheet.close();
      notifyDataChanged();
    });
  }
  const s = sub ?? {};
  currency = s.currency ?? "USD";
  q("#sf-title").textContent = sub ? "Editar suscripción" : "Nueva suscripción";
  q("#sf-templates").hidden = Boolean(sub);
  q("#sf-name").value = s.name ?? "";
  q("#sf-amount").value = sub ? centsToInput(s.amount_cents) : "";
  q("#sf-frequency").value = s.frequency ?? "monthly";
  q("#sf-day").value = s.billing_day ?? new Date().getDate();
  q("#sf-delete").hidden = !sub;
  q("#sf-error").textContent = "";
  syncCurrency();
  icons();
  sheet.open();
}

function init() {
  $("add-sub").addEventListener("click", () => openSheet());
  document.addEventListener("click", async (e) => {
    const toggle = e.target.closest("[data-toggle]");
    if (toggle) {
      // Pausar / reactivar sin abrir la hoja
      const sub = subs.find((s) => s.id === Number(toggle.dataset.toggle));
      toggle.setAttribute("aria-checked", !sub.active);
      await api(`/api/subscriptions/${sub.id}`, { method: "PATCH", body: { active: !sub.active } });
      toast(sub.active ? `${sub.name} pausada` : `${sub.name} activada`);
      notifyDataChanged();
      return;
    }
    const row = e.target.closest("[data-sub]");
    if (row) openSheet(subs.find((s) => s.id === Number(row.dataset.sub)));
    if (e.target.closest("[data-new]")) openSheet();
  });
  onDataChanged(load);
  load();
}

if (mountShell()) init();
