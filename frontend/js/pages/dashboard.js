// dashboard.js · Pantalla de inicio: resumen, gráficos, metas, comida y hoy.

import { api } from "../api.js";
import { openExpenseSheet } from "../expense-form.js";
import {
  centsToInput, longToday, money, moneyExact, parseMoney, shortDate, shortRange, todayISO,
} from "../format.js";
import { openIncomeSheet } from "../income-form.js";
import { categoryLabel, CATEGORY_COLOR, EXTRA_CATEGORY_LABELS, getCategories } from "../labels.js";
import { mountShell } from "../shell.js";
import {
  countUp, createSheet, css, esc, fillBars, icons, notifyDataChanged, onDataChanged, toast,
} from "../ui.js";

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

// --- Tu plata hoy ---
// El backend (services/cashflow.py) hace todas las cuentas; acá solo se dibuja.
const EVENT_ICON = {
  income: "banknote", advance: "banknote", aguinaldo: "gift", fixed: "house", subscription: "repeat",
};

function upcomingList(m) {
  const rows = m.upcoming.slice(0, 5).map((e) => `
    <li class="flex items-center gap-2">
      <span class="muted text-xs w-12 shrink-0">${shortDate(e.date)}</span>
      <i data-lucide="${EVENT_ICON[e.kind] ?? "circle"}" class="w-3.5 h-3.5 shrink-0 ${e.amount_cents > 0 ? "text-success" : "muted"}"></i>
      <span class="flex-1 min-w-0 truncate">${esc(e.label)}</span>
      <span class="tabular-nums ${e.amount_cents > 0 ? "text-success" : ""}">${e.amount_cents > 0 ? "+" : "−"}${money(Math.abs(e.amount_cents))}</span>
    </li>`);
  if (m.upcoming.length > 5) rows.push(`<li class="muted text-xs">y ${m.upcoming.length - 5} más…</li>`);
  if (m.usual_spending_cents) rows.push(`
    <li class="flex items-center gap-2 pt-1.5 mt-1.5 border-t" style="border-color:var(--border)">
      <span class="w-12 shrink-0"></span><i data-lucide="shopping-bag" class="w-3.5 h-3.5 muted shrink-0"></i>
      <span class="flex-1 muted">Tu día a día (estimado)</span>
      <span class="tabular-nums muted">−${money(m.usual_spending_cents)}</span></li>`);
  return rows.length ? `<ul class="space-y-1.5 text-sm">${rows.join("")}</ul>`
    : `<p class="muted text-sm">No hay cobros ni cuentas programadas hasta fin de mes.</p>`;
}

function renderMoney() {
  const m = overview.money;
  const box = $("money");
  if (!m.has_balance) {
    box.innerHTML = `
      <div class="flex flex-col md:flex-row md:items-center gap-4">
        <span class="icon-badge bg-primary-soft text-primary" style="width:52px;height:52px"><i data-lucide="wallet"></i></span>
        <div class="flex-1">
          <h2 class="font-display text-xl font-bold">¿Cuánta plata tenés hoy?</h2>
          <p class="muted">Sumá tus cuentas y el efectivo. Con eso te digo cuánto podés gastar por día y cuánto ahorrar hasta fin de mes.</p>
        </div>
        <button class="btn btn-primary" data-balance><i data-lucide="plus" class="w-4 h-4"></i>Cargar mi saldo</button>
      </div>`;
    return;
  }
  const end = shortDate(m.month_end);
  const since = [
    m.since_income_cents ? `<span class="text-success">+${money(m.since_income_cents)}</span>` : "",
    m.since_spent_cents ? `−${money(m.since_spent_cents)}` : "",
  ].filter(Boolean).join(" · ");
  const short = m.short_cents > 0;

  box.innerHTML = `
    <div class="grid gap-5 xl:gap-8 md:grid-cols-[13rem_1fr] xl:grid-cols-[13rem_1fr_17rem]">
      <div>
        <div class="flex items-center gap-2 muted text-sm"><i data-lucide="wallet" class="w-4 h-4"></i>Tu plata hoy</div>
        <div class="font-display text-4xl font-bold mt-1 ${m.current_cents < 0 ? "text-danger" : ""}" id="money-current">$ 0</div>
        <p class="muted text-xs mt-1">Cargaste ${money(m.balance_cents)} el ${shortDate(m.balance_date)}${since ? ` · desde entonces ${since}` : ""}</p>
        <button class="btn btn-ghost text-sm mt-3" data-balance><i data-lucide="refresh-cw" class="w-4 h-4"></i>Actualizar saldo</button>
      </div>

      <div class="grid grid-cols-2 gap-3 content-start">
        <div class="rounded-xl p-4 ${short ? "bg-danger-soft" : "bg-primary-soft"}">
          <div class="muted text-sm">${short ? "Máximo por día" : "Para gastar por día"}</div>
          <div class="font-display text-2xl font-bold ${short ? "text-danger" : "text-primary"}" id="money-daily">$ 0</div>
          <div class="muted text-xs mt-1">hasta el ${end} (${m.days_left} ${m.days_left === 1 ? "día" : "días"})${short ? "" : " · tu ritmo habitual"}</div>
        </div>
        <div class="rounded-xl p-4 bg-accent-soft">
          <div class="muted text-sm">Podés ahorrar</div>
          <div class="font-display text-2xl font-bold text-accent" id="money-save">$ 0</div>
          <div class="bar mt-2" style="height:6px"><span data-fill="${m.save_pct}" style="background:var(--accent)"></span></div>
          <div class="muted text-xs mt-1"><b class="text-accent">${m.save_pct}%</b> de tu plata libre (${money(Math.max(m.free_cents, 0))})</div>
        </div>
        ${short ? `<p class="col-span-2 text-sm rounded-xl bg-danger-soft p-3 flex gap-2 items-start">
            <i data-lucide="circle-alert" class="w-4 h-4 text-danger mt-0.5 shrink-0"></i>
            <span>A tu ritmo de siempre te faltarían <b>${money(m.short_cents)}</b> para llegar a fin de mes. Para llegar, gastá como máximo lo de arriba por día.</span></p>` : ""}
        ${m.has_spending_history ? "" : `<p class="col-span-2 muted text-xs">Todavía no tengo historial de tus gastos del día a día: a medida que los anotes, el cálculo se ajusta.</p>`}
      </div>

      <div class="md:col-span-2 xl:col-span-1">
        <div class="text-sm font-medium mb-2">Hasta fin de mes</div>
        ${upcomingList(m)}
      </div>
    </div>`;
  countUp($("money-current"), m.current_cents);
  countUp($("money-daily"), m.daily_spending_cents);
  countUp($("money-save"), m.can_save_cents);
}

let balanceSheet;
function openBalanceSheet() {
  balanceSheet ??= createSheet(`
    <form id="balance-form" novalidate>
      <h3 class="font-display text-xl font-bold mb-1">¿Cuánta plata tenés hoy?</h3>
      <p class="muted text-sm">Sumá tus cuentas y el efectivo. Si estás en rojo, poné el número con un "-" adelante.</p>
      <input id="bs-amount" class="amount-input my-5" inputmode="decimal" placeholder="0" aria-label="Saldo de hoy" autofocus />
      <p class="muted text-xs mb-4">Desde ahora, VaultBase resta los gastos que anotes y suma tus cobros (sueldo, adelanto) en su día.
        Cuando quieras, lo actualizás mirando tu cuenta.</p>
      <p class="form-error mb-2" id="bs-error"></p>
      <button class="btn btn-primary w-full">Guardar</button>
      <button type="button" class="btn btn-ghost w-full mt-2 text-sm" id="bs-clear">Dejar de usar "Tu plata hoy"</button>
    </form>`, { label: "Saldo de hoy" });
  const q = (s) => balanceSheet.el.querySelector(s);
  if (!balanceSheet.ready) {
    balanceSheet.ready = true;
    const save = async (value, message) => {
      await api("/api/users/me", { method: "PATCH", body: { balance_cents: value } });
      toast(message);
      balanceSheet.close();
      notifyDataChanged();
    };
    q("#balance-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const value = parseMoney(q("#bs-amount").value);
      if (value === null) return (q("#bs-error").textContent = "Escribí un monto (ej: 25.000).");
      await save(value, "Saldo actualizado");
    });
    q("#bs-clear").addEventListener("click", () => save(null, "Listo, ya no se usa tu saldo"));
  }
  const m = overview.money;
  // Precargamos el saldo estimado, redondeado a pesos (sin centésimos)
  q("#bs-amount").value = m.has_balance ? centsToInput(Math.round(m.current_cents / 100) * 100) : "";
  q("#bs-clear").hidden = !m.has_balance;
  q("#bs-error").textContent = "";
  balanceSheet.open();
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
          label: (c) => `${c.dataset.label}: ${money(c.raw * 100)}${future[c.dataIndex] ? " (estimado)" : ""}`,
          // En junio y diciembre aclaramos cuánto es aguinaldo
          afterLabel: (c) => (c.datasetIndex === 0 && months[c.dataIndex].aguinaldo_cents
            ? `Incluye aguinaldo: ${money(months[c.dataIndex].aguinaldo_cents)}` : "") } },
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
  $("food-pct").innerHTML = `<i data-lucide="sliders-horizontal" class="w-3.5 h-3.5"></i>${f.percentage}% · Ajustar`;
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

// --- Cambiar el % de comida (se guarda en tu perfil) ---
let foodSheet;
function openFoodSheet() {
  const disposable = Math.max(overview.capacity.disposable_income_cents, 0);
  foodSheet ??= createSheet(`
    <h3 class="font-display text-xl font-bold mb-1">Presupuesto de comida</h3>
    <p class="muted text-sm mb-5">Qué parte de tu ingreso disponible (ingresos − fijos) querés destinar a comida.</p>
    <div class="text-center mb-2"><span class="font-display text-5xl font-bold text-primary" id="fs-pct"></span></div>
    <div class="text-center muted mb-5" id="fs-amount"></div>
    <input type="range" min="5" max="70" step="1" id="fs-range" class="w-full mb-6" style="accent-color:var(--primary)" aria-label="Porcentaje" />
    <button class="btn btn-primary w-full" id="fs-save">Guardar</button>`, { label: "Presupuesto de comida" });
  const q = (s) => foodSheet.el.querySelector(s);
  const update = () => {
    const pct = Number(q("#fs-range").value);
    q("#fs-pct").textContent = `${pct}%`;
    q("#fs-amount").textContent = `${money((disposable * pct) / 100)} por mes · ${money((disposable * pct) / 100 / 4.33)} por semana`;
  };
  if (!foodSheet.ready) {
    foodSheet.ready = true;
    q("#fs-range").addEventListener("input", update);
    q("#fs-save").addEventListener("click", async () => {
      await api("/api/users/me", { method: "PATCH", body: { food_budget_pct: Number(q("#fs-range").value) } });
      toast("Presupuesto de comida actualizado");
      foodSheet.close();
      notifyDataChanged();
    });
  }
  q("#fs-range").value = overview.food.percentage;
  update();
  foodSheet.open();
}

async function load() {
  overview = await api("/api/finance/overview");
  renderMoney();
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
  $("food-pct").addEventListener("click", openFoodSheet);
  $("money").addEventListener("click", (e) => { if (e.target.closest("[data-balance]")) openBalanceSheet(); });
  onDataChanged(load);
  document.addEventListener("vb:theme", renderCharts);  // los colores del gráfico cambian con el tema
  loadRate();
  load();
}

if (mountShell()) init();
