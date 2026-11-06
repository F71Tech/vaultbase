// movimientos.js · Lista de gastos (fijos y del día a día) e ingresos, por mes.

import { api } from "../api.js";
import { commissionAmount, openCommissionSheet, payDateOf } from "../commission-form.js";
import { openExpenseSheet } from "../expense-form.js";
import { friendlyDay, money, moneyExact, monthLabel, shortDate, toISO } from "../format.js";
import { openIncomeSheet } from "../income-form.js";
import { openPaySheet } from "../pay-form.js";
import { categoryLabel, CATEGORY_COLOR, FREQUENCY, getCategories } from "../labels.js";
import { mountShell } from "../shell.js";
import { countUp, esc, icons, onDataChanged } from "../ui.js";

const now = new Date();
const view = { year: now.getFullYear(), month: now.getMonth() + 1, tab: "expenses", category: null };
let cats;
let cache = {
  variable: [], fixed: [], incomes: [], allIncomes: [], summary: null, commissions: [], payRecords: [], salary: null,
};

const $ = (id) => document.getElementById(id);

function monthRange() {
  const first = new Date(view.year, view.month - 1, 1);
  const last = new Date(view.year, view.month, 0);
  return { from: toISO(first), to: toISO(last) };
}

// Un gasto fijo "vale" en este mes si empezó antes del fin de mes y no terminó antes del inicio
const activeInMonth = (item, startKey, { from, to }) =>
  item[startKey] <= to && (!item.end_date || item.end_date >= from);

/** Fila de la lista: ícono de la categoría, nombre, detalle y monto. */
function expenseRow(e, detail) {
  const cat = cats.byKey[e.category];
  const color = `var(${CATEGORY_COLOR[e.category] || "--cat-7"})`;
  const usd = e.currency === "USD";
  const pesos = usd && e.exchange_rate ? `<div class="muted text-xs">≈ ${money(e.amount_cents * e.exchange_rate)}</div>` : "";
  // Título: la descripción; si no hay, la subcategoría (o la categoría)
  const sub = cat?.subcategories.find((s) => s.key === e.subcategory);
  const title = e.description || sub?.label || cat?.label || e.category;
  return `
    <button class="row" data-expense="${e.id}">
      <span class="icon-badge" style="background:color-mix(in srgb, ${color} 16%, transparent);color:${color}">
        <i data-lucide="${cat?.icon || "circle"}"></i></span>
      <span class="flex-1 min-w-0">
        <span class="block font-medium truncate">${esc(title)}${e.kind === "one_off"
          ? ` <span class="chip text-accent align-middle" style="padding:1px 8px;font-size:.65rem">Puntual</span>` : ""}${e.paid_with_ticket
          ? ` <span class="chip text-accent align-middle" style="padding:1px 8px;font-size:.65rem">Ticket</span>` : ""}</span>
        <span class="block muted text-xs truncate">${esc(detail)}</span>
      </span>
      <span class="text-right font-semibold">${moneyExact(e.amount_cents, e.currency)}${pesos}</span>
    </button>`;
}

const emptyState = (icon, text) => `
  <div class="text-center py-8 muted fade">
    <i data-lucide="${icon}" class="w-10 h-10 mx-auto mb-3 opacity-60"></i><p>${text}</p>
  </div>`;

function renderCategoryFilter() {
  // Solo mostramos categorías que tienen gastos este mes
  const used = new Set([...cache.variable, ...cache.fixed].map((e) => e.category));
  const chips = cats.list.filter((c) => used.has(c.key));
  $("category-filter").innerHTML = chips.length < 2 ? "" : [
    `<button class="chip shrink-0" data-filter="" aria-pressed="${!view.category}">Todas</button>`,
    ...chips.map((c) => `<button class="chip shrink-0" data-filter="${c.key}" aria-pressed="${view.category === c.key}">
      <i data-lucide="${c.icon}" class="w-3.5 h-3.5"></i>${esc(c.label)}</button>`),
  ].join("");
}

function renderExpenses() {
  const match = (e) => !view.category || e.category === view.category;

  const fixed = cache.fixed.filter(match);
  $("fixed-list").innerHTML = fixed.length
    ? fixed.map((e) => expenseRow(e, `${cats.byKey[e.category]?.label} · desde ${shortDate(e.date)}${e.end_date ? " hasta " + shortDate(e.end_date) : ""}`)).join("")
    : emptyState("house", "Sin gastos fijos. Agregá el alquiler, UTE, internet…");

  // Gastos del día a día, agrupados por día con su total
  const variable = cache.variable.filter(match);
  // Agrupamos por fecha: { "2026-11-02": [gasto, gasto], "2026-11-01": [...] }
  const byDay = new Map();
  for (const e of variable) byDay.set(e.date, [...(byDay.get(e.date) || []), e]);
  $("variable-list").innerHTML = variable.length
    ? [...byDay].map(([day, items]) => {
        const total = items.reduce((s, e) => s + e.amount_cents * (e.currency === "USD" ? e.exchange_rate || 0 : 1), 0);
        return `<div class="mt-3 first:mt-0">
          <div class="flex justify-between text-xs uppercase tracking-wide muted px-2 mb-1">
            <span>${friendlyDay(day)}</span><span>${money(total)}</span></div>
          ${items.map((e) => expenseRow(e, e.description ? categoryLabel(cats, e.category, e.subcategory) : cats.byKey[e.category]?.label)).join("")}
        </div>`;
      }).join("")
    : emptyState("receipt", "Todavía no hay gastos este mes. Tocá <b>+</b> para anotar el primero.");

  renderCategoryFilter();
  if (cache.summary) {
    countUp($("total-variable"), cache.summary.variable_expenses_cents);
    countUp($("total-fixed"), cache.summary.fixed_expenses_cents);
  }
  icons();
}

// Debajo de cada sueldo mensual: el último cobro real y el botón para anotar uno nuevo
function payRecordLine(income) {
  if (income.frequency !== "monthly" || income.food_only) return "";
  const last = cache.payRecords.filter((r) => r.income_id === income.id && r.kind === "pay")
    .sort((a, b) => b.date.localeCompare(a.date))[0];
  return `
    <div class="flex items-center justify-between gap-2 pl-14 pr-2 -mt-1 mb-2 text-xs">
      <span class="muted">${last ? `Último cobro real: <b class="text-primary">${money(last.amount_cents)}</b> (${shortDate(last.date)}) · los próximos se estiman con este`
                                  : "Sin cobros reales anotados: se usa el monto de arriba"}</span>
      <button class="chip shrink-0" data-pay-income="${income.id}"><i data-lucide="badge-check" class="w-3.5 h-3.5"></i>Anotar cobro</button>
    </div>`;
}

function renderIncomes() {
  const list = cache.incomes;
  $("income-list").innerHTML = list.length
    ? list.map((i) => `
      <button class="row" data-income="${i.id}">
        <span class="icon-badge bg-primary-soft text-primary"><i data-lucide="trending-up"></i></span>
        <span class="flex-1 min-w-0">
          <span class="block font-medium truncate">${esc(i.source)}</span>
          <span class="block muted text-xs">${i.previous_money ? "Ya la tenías · no cuenta como ingreso del mes" : `${i.food_only ? "Ticket · solo comida · " : ""}${FREQUENCY[i.frequency]} · ${i.frequency === "one_time" ? shortDate(i.start_date) : "desde " + shortDate(i.start_date)}${i.end_date ? " hasta " + shortDate(i.end_date) : ""}`}</span>
        </span>
        <span class="font-semibold text-primary">${moneyExact(i.amount_cents, i.currency)}</span>
      </button>${payRecordLine(i)}`).join("")
    : emptyState("wallet", "Cargá tu sueldo u otros ingresos para que los cálculos funcionen.");
  if (cache.summary) countUp($("total-income"), cache.summary.income_cents);
  renderCommissions();
  icons();
}

// Comisiones por semana (solo si tu sueldo tiene comisiones o ya anotaste alguna)
function renderCommissions() {
  const { commissions, salary } = cache;
  $("commissions-card").hidden = !salary && !commissions.length;
  if ($("commissions-card").hidden) return;
  const floor = salary?.commission_floor_cents;
  $("commissions-hint").textContent = floor
    ? `Las semanas que no anotes cuentan como tu bono mínimo (${money(floor)}). Para planificar se usa el mínimo de cada rango.`
    : "Para planificar se usa el mínimo de cada rango; cuando sepas el monto real, cargalo.";
  const day = salary?.pay_day ?? 30;
  $("commission-list").innerHTML = commissions.length ? commissions.map((c) => `
    <button class="row" data-commission="${c.id}">
      <span class="icon-badge bg-primary-soft text-primary"><i data-lucide="${c.actual_cents != null ? "badge-check" : "trending-up"}"></i></span>
      <span class="flex-1 min-w-0">
        <span class="block font-medium truncate">Semana del ${shortDate(c.week_start)}</span>
        <span class="block muted text-xs truncate">${c.note ? `${esc(c.note)} · ` : ""}se cobra el ${shortDate(payDateOf(c.week_start, day))}</span>
      </span>
      <span class="text-right">
        <span class="block font-semibold text-primary">${commissionAmount(c)}</span>
        <span class="block muted text-xs">${c.actual_cents != null ? "real" : "estimado"}</span>
      </span>
    </button>`).join("")
    : emptyState("trending-up", "Anotá la comisión de cada semana (un rango si no sabés el monto exacto).");
}

async function load() {
  $("month-label").textContent = monthLabel(view.year, view.month);
  const range = monthRange();
  // Pedimos todo en paralelo (Promise.all) en vez de uno por uno: es más rápido
  const [monthItems, fixedAll, incomes, summary, commissions, payRecords] = await Promise.all([
    api(`/api/expenses?from_date=${range.from}&to_date=${range.to}&kind=variable&kind=one_off`),
    api("/api/expenses?kind=fixed&limit=1000"),
    api("/api/incomes"),
    api(`/api/finance/month?year=${view.year}&month=${view.month}`),
    api("/api/commissions"),
    api("/api/pay-records"),
  ]);
  cache = {
    commissions,
    payRecords,
    salary: incomes.find((i) => i.commission_floor_cents != null),  // el sueldo con comisiones
    allIncomes: incomes,
    variable: monthItems,
    fixed: fixedAll.filter((e) => activeInMonth(e, "date", range)),
    incomes: incomes.filter((i) => i.previous_money || (i.frequency === "one_time"
      ? i.start_date >= range.from && i.start_date <= range.to
      : activeInMonth(i, "start_date", range))),
    summary,
  };
  renderExpenses();
  renderIncomes();
}

function setTab(tab) {
  view.tab = tab;
  document.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.tab === tab));
  $("tab-expenses").hidden = tab !== "expenses";
  $("tab-incomes").hidden = tab !== "incomes";
}

function moveMonth(delta) {
  const d = new Date(view.year, view.month - 1 + delta, 1);
  view.year = d.getFullYear();
  view.month = d.getMonth() + 1;
  load();
}

async function init() {
  cats = await getCategories();
  const tabParam = new URLSearchParams(location.search).get("tab");
  setTab(tabParam === "incomes" ? "incomes" : "expenses");

  document.addEventListener("click", (e) => {
    const t = e.target;
    const exp = t.closest("[data-expense]");
    const inc = t.closest("[data-income]");
    const filter = t.closest("[data-filter]");
    const tab = t.closest("[data-tab]");
    if (exp) {
      const id = Number(exp.dataset.expense);
      openExpenseSheet([...cache.variable, ...cache.fixed].find((x) => x.id === id));
    }
    if (inc) openIncomeSheet(cache.incomes.find((x) => x.id === Number(inc.dataset.income)));
    const payBtn = t.closest("[data-pay-income]");
    if (payBtn) openPaySheet(cache.allIncomes.find((x) => x.id === Number(payBtn.dataset.payIncome)));
    const com = t.closest("[data-commission]");
    if (com) openCommissionSheet(cache.commissions.find((x) => x.id === Number(com.dataset.commission)),
      { salaryPayDay: cache.salary?.pay_day ?? 30 });
    if (filter) { view.category = filter.dataset.filter || null; renderExpenses(); }
    if (tab) setTab(tab.dataset.tab);
  });
  $("prev-month").addEventListener("click", () => moveMonth(-1));
  $("next-month").addEventListener("click", () => moveMonth(1));
  $("add-variable").addEventListener("click", () => openExpenseSheet());
  $("add-fixed").addEventListener("click", () => openExpenseSheet(null, { kind: "fixed" }));
  $("add-income").addEventListener("click", () => openIncomeSheet());
  $("add-one-time").addEventListener("click", () => openIncomeSheet(null, { frequency: "one_time" }));
  $("add-commission").addEventListener("click", () => openCommissionSheet(null, { salaryPayDay: cache.salary?.pay_day ?? 30 }));
  onDataChanged(load);

  load();
}

if (mountShell()) init();
