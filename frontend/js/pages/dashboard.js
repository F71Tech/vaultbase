// dashboard.js · Pantalla de inicio: resumen, gráficos, metas, comida y hoy.

import { api } from "../api.js";
import { openExpenseSheet } from "../expense-form.js";
import { longToday, money, moneyExact, shortDate, shortRange, todayISO } from "../format.js";
import { openIncomeSheet } from "../income-form.js";
import { categoryLabel, CATEGORY_COLOR, EXTRA_CATEGORY_LABELS, getCategories } from "../labels.js";
import { mountShell } from "../shell.js";
import { countUp, css, esc, fillBars, icons, onDataChanged } from "../ui.js";

const $ = (id) => document.getElementById(id);
const MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
let cats;
let overview;
let charts = {};

// --- Cotización del dólar con "hace cuánto" ---
function relativeTime(iso) {
  const minutes = Math.round((Date.now() - new Date(iso)) / 60000);
  if (minutes < 1) return "recién";
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `hace ${hours} h` : `hace ${Math.round(hours / 24)} d`;
}
async function loadRate() {
  try {
    const r = await api("/api/exchange-rate");
    const value = r.rate.toLocaleString("es-UY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    $("usd-chip").lastElementChild.textContent = `USD $ ${value} · ${r.source} · ${relativeTime(r.fetched_at)}`;
    $("usd-chip").title = `Cotización del ${shortDate(r.rate_date)}`;
  } catch {
    $("usd-chip").lastElementChild.textContent = "Cotización no disponible";
  }
}

// --- Tarjetas de arriba ---
function renderStats() {
  const m = overview.current_month;
  countUp($("stat-income"), m.income_cents);
  countUp($("stat-expenses"), m.total_expenses_cents);
  countUp($("stat-balance"), m.balance_cents);
  countUp($("stat-savings"), overview.capacity.monthly_savings_cents);
  $("stat-balance").className = `font-display text-xl md:text-2xl font-bold ${m.balance_cents < 0 ? "text-danger" : "text-primary"}`;
  $("onboarding").hidden = overview.capacity.recurring_income_cents > 0 || m.income_cents > 0;
}

// --- Gráficos (Chart.js) ---
function renderCharts() {
  Object.values(charts).forEach((c) => c.destroy());
  Chart.defaults.font.family = "Inter";
  Chart.defaults.color = css("--muted");

  // Dona: gastos del mes por categoría (de mayor a menor)
  const entries = Object.entries(overview.current_month.by_category).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  $("donut-wrap").hidden = !entries.length;
  $("donut-empty").hidden = entries.length > 0;
  const label = (key) => EXTRA_CATEGORY_LABELS[key] || cats.byKey[key]?.label || key;
  const color = (key) => css(CATEGORY_COLOR[key] || "--cat-7");
  if (entries.length) {
    charts.donut = new Chart($("donut"), {
      type: "doughnut",
      data: {
        labels: entries.map(([k]) => label(k)),
        datasets: [{ data: entries.map(([, v]) => v / 100), backgroundColor: entries.map(([k]) => color(k)),
                     borderColor: css("--surface"), borderWidth: 3, hoverOffset: 6 }],
      },
      options: {
        cutout: "72%",
        plugins: { legend: { display: false },
                   tooltip: { callbacks: { label: (c) => ` ${money(c.raw * 100)}` } } },
        animation: { animateRotate: true, duration: 1200, easing: "easeOutCubic" },
      },
    });
    countUp($("donut-total"), total);
    $("legend").innerHTML = entries.map(([k, v]) => `
      <li class="flex items-center justify-between gap-2"><span class="flex items-center gap-2 min-w-0">
        <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${color(k)}"></span>
        <span class="truncate">${esc(label(k))}</span></span>
        <span class="muted shrink-0">${money(v)} · ${Math.round((v / total) * 100)}%</span></li>`).join("");
  }

  // Barras: ingresos vs gastos de cada mes; los meses futuros, punteados
  const months = overview.year.months;
  const future = months.map((m) => m.projected);
  $("year-label").textContent = overview.year.year;
  countUp($("year-balance"), overview.year.balance_cents);
  charts.bars = new Chart($("bars"), {
    type: "bar",
    data: {
      labels: MONTHS,
      datasets: [
        { label: "Ingresos", data: months.map((m) => m.income_cents / 100), borderRadius: 6, borderSkipped: false,
          backgroundColor: css("--primary-soft"), borderColor: css("--primary"), borderWidth: 1.5 },
        { label: "Gastos", data: months.map((m) => m.total_expenses_cents / 100), borderRadius: 6, borderSkipped: false,
          backgroundColor: future.map((f) => (f ? "transparent" : css("--accent"))),
          borderColor: css("--accent"), borderWidth: future.map((f) => (f ? 1.5 : 0)) },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
        tooltip: { callbacks: {
          label: (c) => `${c.dataset.label}: ${money(c.raw * 100)}${future[c.dataIndex] ? " (estimado)" : ""}` } },
      },
      scales: {
        x: { grid: { display: false } },
        // suggestedMax evita un eje con "$ 0,1" cuando todavía no hay datos
        y: { grid: { color: css("--border") }, beginAtZero: true, suggestedMax: 10000,
             ticks: { callback: (v) => (v >= 1000 ? `$ ${v / 1000}k` : `$ ${v}`) } },
      },
      animation: { duration: 1000, easing: "easeOutQuart", delay: (ctx) => ctx.dataIndex * 45 },
    },
  });
}

// --- Metas (las 3 primeras) ---
const GOAL_STATUS = {
  completed: ["text-success", "¡Cumplida!"], on_track: ["text-primary", "En camino"],
  behind: ["text-danger", "Atrasada"], no_deadline: ["muted", "Sin fecha límite"],
  unreachable: ["text-danger", "Sin ahorro disponible"],
};
function renderGoals() {
  const goals = overview.goals.slice(0, 3);
  $("goals").innerHTML = goals.length ? goals.map((g) => {
    const [cls, text] = GOAL_STATUS[g.status];
    const eta = g.estimated_date && g.status !== "completed"
      ? `Llegás en ${new Date(g.estimated_date + "T00:00").toLocaleDateString("es-UY", { month: "short", year: "numeric" })}` : "";
    return `<div>
      <div class="flex justify-between items-baseline gap-2 mb-2">
        <span class="font-medium truncate">${esc(g.name)}</span>
        <span class="text-sm muted shrink-0">${Math.round(g.progress_pct)}%</span></div>
      <div class="bar"><span data-fill="${g.progress_pct}" style="background:${g.status === "completed" ? "var(--success)" : "var(--accent)"}"></span></div>
      <div class="flex justify-between mt-2 text-xs"><span class="${cls}">● ${text}</span><span class="muted">${eta}</span></div>
    </div>`;
  }).join("") : `<div class="text-center muted py-6"><i data-lucide="target" class="w-9 h-9 mx-auto mb-2 opacity-60"></i>
      <p class="mb-3">Todavía no tenés metas.</p><a href="/metas.html" class="btn btn-ghost text-sm">Crear una meta</a></div>`;
}

// --- Comida por semana ---
function renderFood() {
  const f = overview.food;
  $("food-pct").textContent = `${f.percentage}% del disponible`;
  countUp($("food-remaining"), f.remaining_cents);
  $("food-remaining").classList.toggle("text-danger", f.remaining_cents < 0);
  $("food-caption").textContent = f.remaining_cents < 0
    ? `te pasaste de ${money(f.monthly_budget_cents)}` : `te quedan de ${money(f.monthly_budget_cents)}`;
  $("food-weeks").innerHTML = f.weeks.map((w) => {
    const pct = w.budget_cents ? Math.min((w.spent_cents / w.budget_cents) * 100, 100) : 0;
    const over = w.spent_cents > w.budget_cents;
    return `<div>
      <div class="flex justify-between text-sm mb-1.5">
        <span class="${w.is_current ? "font-semibold" : "muted"}">${shortRange(w.start, w.end)}${w.is_current ? ' <span class="text-primary">· ahora</span>' : ""}</span>
        <span class="${over ? "text-danger" : "muted"}">${money(w.spent_cents)} / ${money(w.budget_cents)}</span></div>
      <div class="bar"><span data-fill="${pct}" style="background:${over ? "var(--danger)" : "var(--primary)"}"></span></div>
    </div>`;
  }).join("");
}

// --- Gastos de hoy ---
async function renderToday() {
  const items = await api(`/api/expenses?from_date=${todayISO()}&to_date=${todayISO()}&kind=variable`);
  const total = items.reduce((s, e) => s + e.amount_cents * (e.currency === "USD" ? e.exchange_rate || 0 : 1), 0);
  countUp($("today-total"), total);
  $("today-list").innerHTML = items.length ? items.slice(0, 6).map((e) => `
    <button class="row" data-expense='${e.id}'>
      <span class="icon-badge bg-primary-soft text-primary"><i data-lucide="${cats.byKey[e.category]?.icon || "circle"}"></i></span>
      <span class="flex-1 min-w-0 truncate">${esc(e.description || categoryLabel(cats, e.category, e.subcategory))}</span>
      <span class="font-semibold">${moneyExact(e.amount_cents, e.currency)}</span>
    </button>`).join("")
    : `<div class="text-center muted py-6"><p class="mb-3">Nada anotado hoy.</p>
       <button class="btn btn-primary text-sm" id="today-add"><i data-lucide="plus" class="w-4 h-4"></i>Anotar gasto</button></div>`;
  $("today-list").onclick = (ev) => {
    const row = ev.target.closest("[data-expense]");
    if (row) openExpenseSheet(items.find((x) => x.id === Number(row.dataset.expense)));
    if (ev.target.closest("#today-add")) openExpenseSheet();
  };
  icons();
}

async function load() {
  overview = await api("/api/finance/overview");
  renderStats();
  renderCharts();
  renderGoals();
  renderFood();
  await renderToday();
  fillBars();
  icons();
}

async function init() {
  $("today").textContent = longToday();
  cats = await getCategories();
  $("onboard-income").addEventListener("click", () => openIncomeSheet());
  onDataChanged(load);
  document.addEventListener("vb:theme", renderCharts);  // los colores del gráfico cambian con el tema
  loadRate();
  load();
}

if (mountShell()) init();
