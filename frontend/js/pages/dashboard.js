// dashboard.js · Pantalla de inicio: resumen, gráficos, metas, comida y hoy.

import { api } from "../api.js";
import { openExpenseSheet } from "../expense-form.js";
import { longToday, money, moneyExact, shortDate, shortRange, todayISO } from "../format.js";
import { openIncomeSheet } from "../income-form.js";
import { openPaySheet } from "../pay-form.js";
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
  income: "banknote", advance: "banknote", aguinaldo: "gift", commission: "trending-up", fixed: "house",
  subscription: "repeat", one_off: "shopping-bag",
};

function upcomingList(m) {
  const rows = m.upcoming.slice(0, 5).map((e) => `
    <li class="flex items-center gap-2">
      <span class="muted text-xs w-12 shrink-0">${shortDate(e.date)}</span>
      <i data-lucide="${EVENT_ICON[e.kind] ?? "circle"}" class="w-3.5 h-3.5 shrink-0 ${e.amount_cents > 0 ? "text-success" : "muted"}"></i>
      <span class="flex-1 min-w-0 truncate">${esc(e.label)}</span>
      <span class="tabular-nums ${e.amount_cents > 0 ? "text-success" : ""}">${e.amount_cents > 0 ? "+" : "−"}${money(Math.abs(e.amount_cents))}${e.amount_high_cents && e.amount_high_cents !== e.amount_cents ? ` – ${money(e.amount_high_cents)}` : ""}</span>
    </li>`);
  if (m.upcoming.length > 5) rows.push(`<li class="muted text-xs">y ${m.upcoming.length - 5} más…</li>`);
  if (m.usual_spending_cents) rows.push(`
    <li class="flex items-center gap-2 pt-1.5 mt-1.5 border-t" style="border-color:var(--border)">
      <span class="w-12 shrink-0"></span><i data-lucide="shopping-bag" class="w-3.5 h-3.5 muted shrink-0"></i>
      <span class="flex-1 muted">Tu día a día (estimado)</span>
      <span class="tabular-nums muted">−${money(m.usual_spending_cents)}</span></li>`);
  return rows.length ? `<ul class="space-y-1.5 text-sm">${rows.join("")}</ul>`
    : `<p class="muted text-sm">No hay cobros ni cuentas programadas hasta tu próximo cobro.</p>`;
}

function renderMoney() {
  const m = overview.money;
  const box = $("money");
  // Cuenta nueva sin movimientos: no hay nada que mostrar todavía
  box.hidden = !m.received_cents && !m.spent_cents && !m.upcoming.length;
  if (box.hidden) return;
  const end = shortDate(m.period_end);
  const short = m.short_cents > 0;

  box.innerHTML = payReminder() + `
    <div class="grid gap-5 xl:gap-8 md:grid-cols-[13rem_1fr] xl:grid-cols-[13rem_1fr_17rem]">
      <div>
        <div class="flex items-center gap-2 muted text-sm"><i data-lucide="wallet" class="w-4 h-4"></i>Tu plata hoy</div>
        <div class="font-display text-4xl font-bold mt-1 ${m.current_cents < 0 ? "text-danger" : ""}" id="money-current">$ 0</div>
        <div class="text-xs mt-2 space-y-0.5">
          <div class="flex justify-between gap-3"><span class="muted">Te entró desde el ${shortDate(m.tracked_from)}</span><span class="text-success">+${money(m.received_cents)}</span></div>
          <div class="flex justify-between gap-3"><span class="muted">Gastaste hasta hoy</span><span>−${money(m.spent_cents)}</span></div>
        </div>
        ${m.tracked_from < m.since ? `<p class="muted text-xs mt-1">Incluye lo que te sobró de antes de tu último cobro (${shortDate(m.since)}): la plata no se "reinicia" cada mes.</p>` : ""}
        ${m.current_cents < 0 ? `<div class="mt-3 rounded-xl bg-accent-soft p-3 text-xs">
            <b>¿Tenías plata de antes del ${shortDate(m.tracked_from)}?</b> La app no la conoce, por eso da negativo.
            <button class="text-primary font-semibold block mt-1" data-previous-money>Sumala una vez →</button></div>` : ""}
        ${m.ticket_cents ? `<p class="muted text-xs mt-2"><i data-lucide="ticket" class="inline w-3 h-3 text-accent"></i>
          Sin contar el ticket de alimentación: pagó ${money(m.ticket_used_cents)} de comida y te quedan ${money(m.ticket_left_cents)}.</p>` : ""}
      </div>

      <div class="grid grid-cols-2 gap-3 content-start">
        <div class="rounded-xl p-4 ${short ? "bg-danger-soft" : "bg-primary-soft"}">
          <div class="muted text-sm">${short ? "Máximo por día" : "Para gastar por día"}</div>
          <div class="font-display text-2xl font-bold ${short ? "text-danger" : "text-primary"}" id="money-daily">$ 0</div>
          <div class="text-xs">≈ ${money(m.daily_spending_cents * 7)} por semana</div>
          <div class="muted text-xs mt-1">hasta el ${end} (${m.days_left} ${m.days_left === 1 ? "día" : "días"})${short ? "" : " · tu ritmo habitual"}</div>
        </div>
        <div class="rounded-xl p-4 bg-accent-soft">
          <div class="muted text-sm">Podés ahorrar</div>
          <div class="font-display text-2xl font-bold text-accent" id="money-save">$ 0</div>
          <div class="bar mt-2" style="height:6px"><span data-fill="${m.save_pct}" style="background:var(--accent)"></span></div>
          <div class="muted text-xs mt-1"><b class="text-accent">${m.save_pct}%</b> de tu plata libre (${money(Math.max(m.free_cents, 0))})</div>
          ${m.can_save_high_cents > m.can_save_cents ? `<div class="text-xs mt-1">Hasta <b class="text-success">${money(m.can_save_high_cents)}</b> si tus comisiones vienen altas</div>` : ""}
        </div>
        ${short ? `<p class="col-span-2 text-sm rounded-xl bg-danger-soft p-3 flex gap-2 items-start">
            <i data-lucide="circle-alert" class="w-4 h-4 text-danger mt-0.5 shrink-0"></i>
            <span>A tu ritmo de siempre te faltarían <b>${money(m.short_cents)}</b> para llegar a tu próximo cobro. Para llegar, gastá como máximo lo de arriba por día.</span></p>` : ""}
        ${m.has_spending_history ? "" : `<p class="col-span-2 muted text-xs">Todavía no tengo historial de tus gastos del día a día: a medida que los anotes, el cálculo se ajusta.</p>`}
      </div>

      <div class="md:col-span-2 xl:col-span-1">
        <div class="text-sm font-medium mb-2">Hasta tu próximo cobro <span class="muted font-normal">(${shortDate(m.next_pay)})</span></div>
        ${upcomingList(m)}
      </div>
    </div>`;
  countUp($("money-current"), m.current_cents);
  countUp($("money-daily"), m.daily_spending_cents);
  countUp($("money-save"), m.can_save_cents);
}

// --- Tarjetas de arriba ---
function renderStats() {
  const m = overview.current_month;
  countUp($("stat-income"), m.income_cents);
  countUp($("stat-expenses"), m.total_expenses_cents);
  countUp($("stat-balance"), m.balance_cents);
  // "Podés ahorrar": cuenta tu plata de HOY (lo mismo que la tarjeta de arriba),
  // y abajo, como referencia, lo que te sobra en un mes típico.
  const money_ = overview.money;
  countUp($("stat-savings"), money_.can_save_cents);
  const typical = overview.capacity.monthly_savings_cents;
  $("stat-savings-note").textContent = `hasta tu próximo cobro (${shortDate(money_.next_pay)})`
    + (typical > 0 ? ` · en un mes típico te sobran ${money(typical)}` : "");
  $("stat-balance").className = `font-display text-xl md:text-2xl font-bold ${m.balance_cents < 0 ? "text-danger" : "text-primary"}`;
  // Sin ingresos que se repitan, pero con un cobro único reciente (que no sea
  // "plata que ya tenía"): seguramente es el sueldo cargado como "única vez".
  const noRecurring = overview.capacity.recurring_income_cents <= 0;
  const monthAgo = new Date(Date.now() - 45 * 86400000).toISOString().slice(0, 10);
  oneTimeSalary = noRecurring ? payInfo.incomes.find((i) => i.frequency === "one_time" && !i.food_only
    && i.start_date >= monthAgo && !/ya ten[ií]a/i.test(i.source)) : null;
  $("salary-hint").hidden = !oneTimeSalary;
  if (oneTimeSalary) {
    $("salary-hint").innerHTML = `
      <div class="flex flex-col md:flex-row md:items-center gap-3">
        <span class="icon-badge bg-danger-soft text-danger" style="width:44px;height:44px"><i data-lucide="calendar-x"></i></span>
        <div class="flex-1 text-sm">
          <b>"${esc(oneTimeSalary.source)}" está cargado como "única vez"</b> (${shortDate(oneTimeSalary.start_date)}).
          <span class="muted">Para la app no volvés a cobrar: por eso los ingresos del mes dan $ 0 y el ahorro posible, negativo.
          Si lo cobrás todos los meses, pasalo a <b>Mensual</b> (y anotá el cobro real de cada mes).</span>
        </div>
        <button class="btn btn-primary text-sm" data-fix-salary>Pasarlo a mensual</button>
      </div>`;
  }
  $("onboarding").hidden = Boolean(oneTimeSalary) || overview.capacity.recurring_income_cents > 0 || m.income_cents > 0;
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
  $("food-ticket").hidden = !f.ticket_cents;
  if (f.ticket_cents) {
    const pct = Math.min((f.ticket_used_cents / f.ticket_cents) * 100, 100);
    $("food-ticket").innerHTML = `
      <div class="muted text-xs flex items-center gap-1.5"><i data-lucide="ticket" class="w-3.5 h-3.5 text-accent"></i>Ticket alimentación</div>
      <div class="font-semibold mt-0.5">Te quedan ${money(f.ticket_left_cents)}</div>
      <div class="bar mt-2" style="height:6px"><span data-fill="${pct}" style="background:var(--accent)"></span></div>
      <div class="muted text-xs mt-1">Usaste ${money(f.ticket_used_cents)} de ${money(f.ticket_cents)} este mes</div>`;
  }
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
  const items = await api(`/api/expenses?from_date=${todayISO()}&to_date=${todayISO()}&kind=variable&kind=one_off`);
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

// --- Recordatorio del día de cobro: "¿cuánto te entró?" ---
// Durante la semana después de cada cobro del sueldo, si todavía no anotaste
// el cobro real de ese mes, lo pedimos (así los cálculos usan el número real).
let payInfo = { salary: null, records: [], incomes: [] };
let oneTimeSalary = null;  // el sueldo cargado por error como "única vez" (si lo hay)

function payReminder() {
  const { salary, records } = payInfo;
  const since = overview.money.since;
  if (!salary) return "";
  const days = (Date.now() - new Date(since + "T00:00")) / 86400000;
  const logged = records.some((r) => r.income_id === salary.id && r.kind === "pay" && r.date.slice(0, 7) === since.slice(0, 7));
  if (days > 7 || logged) return "";
  return `
    <div class="mb-4 rounded-xl bg-accent-soft p-3 flex flex-wrap gap-3 items-center">
      <i data-lucide="badge-check" class="w-5 h-5 text-accent shrink-0"></i>
      <span class="flex-1 min-w-[12rem] text-sm"><b>El ${shortDate(since)} cobraste.</b> ¿Cuánto te entró? Anotalo y los cálculos usan el número real.</span>
      <button class="btn btn-primary text-sm py-2" data-pay-now>Anotar cobro</button>
    </div>`;
}

async function load() {
  const [ov, incomes, records] = await Promise.all([
    api("/api/finance/overview"), api("/api/incomes"), api("/api/pay-records"),
  ]);
  overview = ov;
  // El sueldo principal: el ingreso mensual más grande (que no sea el ticket)
  const monthly = incomes.filter((i) => i.frequency === "monthly" && !i.food_only);
  payInfo = { salary: monthly.sort((a, b) => b.amount_cents - a.amount_cents)[0] ?? null, records, incomes };
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
  $("money").addEventListener("click", (e) => {
    if (e.target.closest("[data-pay-now]") && payInfo.salary) openPaySheet(payInfo.salary);
    // Plata que ya tenías antes de usar la app: un ingreso único el día en que arranca el cálculo
    if (e.target.closest("[data-previous-money]")) {
      openIncomeSheet(null, { source: "Plata que ya tenía", frequency: "one_time", start_date: overview.money.tracked_from });
    }
  });
  // "Pasarlo a mensual": abre el ingreso ya cambiado a Mensual, con el día de cobro
  // de ese cobro único (ej: 30). La fecha "desde" queda en ese cobro.
  $("salary-hint").addEventListener("click", (e) => {
    if (!e.target.closest("[data-fix-salary]") || !oneTimeSalary) return;
    openIncomeSheet(oneTimeSalary);
    const freq = document.getElementById("if-frequency");
    freq.value = "monthly";
    freq.dispatchEvent(new Event("change"));
    document.getElementById("if-pay-day").value = Number(oneTimeSalary.start_date.slice(8, 10));
  });
  onDataChanged(load);
  document.addEventListener("vb:theme", renderCharts);  // los colores del gráfico cambian con el tema
  loadRate();
  load();
}

if (mountShell()) init();