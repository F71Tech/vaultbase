// metas.js · Metas de ahorro: progreso, fecha estimada, sumar ahorro y celebrar.

import { api } from "../api.js";
import { centsToInput, money, parseMoney } from "../format.js";
import { mountShell } from "../shell.js";
import {
  celebrate, confirmDialog, countUp, createSheet, esc, fillBars, icons, notifyDataChanged, onDataChanged, toast,
} from "../ui.js";

const $ = (id) => document.getElementById(id);
const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
let goals = [];        // datos crudos (para editar)
let projections = {};  // cálculo del backend, por id
let pendingCelebration = null;

const STATUS = {
  completed: ["text-success", "circle-check", "¡Cumplida!"],
  on_track: ["text-primary", "trending-up", "En camino"],
  behind: ["text-danger", "alarm-clock", "Atrasada"],
  no_deadline: ["muted", "infinity", "Sin fecha límite"],
  unreachable: ["text-danger", "circle-alert", "Sin ahorro disponible"],
};
const monthYear = (iso) => new Date(iso + "T00:00").toLocaleDateString("es-UY", { month: "long", year: "numeric" });

function goalCard(g, p, index) {
  const [cls, icon, text] = STATUS[p.status];
  const pct = Math.min(p.progress_pct, 100);
  const color = p.status === "completed" ? "var(--success)" : "var(--accent)";
  let detail;
  if (p.status === "completed") detail = "Llegaste al objetivo. 🎉";
  else if (p.months_needed == null) detail = "Con tu ahorro actual no llega: revisá gastos o asignale un aporte.";
  else detail = `Llegás en <b>${monthYear(p.estimated_date)}</b> (${p.months_needed} ${p.months_needed === 1 ? "mes" : "meses"}).`;
  const deadline = p.deadline ? `<div class="muted text-sm mt-1">Fecha límite: ${monthYear(p.deadline)}${
    p.required_monthly_for_deadline_cents ? ` · necesitás ${money(p.required_monthly_for_deadline_cents)}/mes` : ""}</div>` : "";

  return `
  <article class="card p-5 rise" style="animation-delay:${0.1 + index * 0.05}s" data-goal="${g.id}">
    <div class="flex gap-4 sm:gap-5 items-center">
      <div class="relative shrink-0 w-24 h-24 sm:w-[120px] sm:h-[120px]">
        <svg class="progress-ring" width="100%" height="100%" viewBox="0 0 120 120" aria-hidden="true">
          <circle class="track" cx="60" cy="60" r="${RADIUS}" />
          <circle class="value" cx="60" cy="60" r="${RADIUS}" stroke="${color}"
                  stroke-dasharray="${CIRCUMFERENCE}" stroke-dashoffset="${CIRCUMFERENCE}" data-ring="${pct}" />
        </svg>
        <div class="absolute inset-0 grid place-items-center font-display text-xl sm:text-2xl font-bold">${Math.round(pct)}%</div>
      </div>
      <div class="min-w-0 flex-1">
        <span class="chip ${cls} mb-2"><i data-lucide="${icon}" class="w-3.5 h-3.5"></i>${text}</span>
        <h2 class="font-display text-xl font-bold truncate">${esc(g.name)}</h2>
        <div class="text-sm mt-1"><b>${money(g.saved_cents)}</b> <span class="muted">de ${money(g.target_cents)}</span></div>
      </div>
    </div>
    <p class="text-sm mt-4">${detail}</p>
    ${deadline}
    ${p.status === "completed" ? "" : `<div class="muted text-sm mt-1">Aporte: ${money(p.monthly_contribution_cents)}/mes ${p.contribution_is_manual ? "(fijo)" : "(automático)"}</div>`}
    <div class="flex gap-2 mt-4">
      ${p.status === "completed" ? "" : `<button class="btn btn-primary flex-1 text-sm" data-add-saving="${g.id}"><i data-lucide="plus" class="w-4 h-4"></i>Sumar ahorro</button>
      <button class="btn btn-ghost text-sm" data-plan="${g.id}"><i data-lucide="map" class="w-4 h-4"></i>Plan</button>`}
      <button class="btn btn-ghost text-sm ${p.status === "completed" ? "flex-1" : ""}" data-edit="${g.id}" aria-label="Editar"><i data-lucide="pencil" class="w-4 h-4"></i>${p.status === "completed" ? "Editar" : ""}</button>
    </div>
  </article>`;
}

function animateRings() {
  document.querySelectorAll("[data-ring]").forEach((c) => {
    const target = CIRCUMFERENCE * (1 - c.dataset.ring / 100);
    requestAnimationFrame(() => setTimeout(() => c.setAttribute("stroke-dashoffset", target), 150));
  });
}

async function load() {
  const [raw, overview] = await Promise.all([api("/api/goals"), api("/api/finance/overview")]);
  goals = raw;
  projections = Object.fromEntries(overview.goals.map((p) => [p.goal_id, p]));

  countUp($("sum-capacity"), overview.capacity.monthly_savings_cents);
  countUp($("sum-allocated"), overview.goals.reduce((s, p) => s + p.monthly_contribution_cents, 0));
  countUp($("sum-saved"), goals.reduce((s, g) => s + g.saved_cents, 0));

  $("goals").innerHTML = goals.length
    ? goals.map((g, i) => goalCard(g, projections[g.id], i)).join("")
    : `<div class="card p-10 text-center md:col-span-2 rise">
        <i data-lucide="target" class="w-12 h-12 mx-auto mb-4 text-accent"></i>
        <h2 class="font-display text-xl font-bold mb-1">Tu primera meta</h2>
        <p class="muted mb-5">Un viaje, un fondo de emergencia, una compra grande… Ponele número y fecha.</p>
        <button class="btn btn-primary" data-new><i data-lucide="plus" class="w-4 h-4"></i>Crear meta</button></div>`;
  icons();
  animateRings();

  if (pendingCelebration) {
    celebrate(document.querySelector(`[data-goal="${pendingCelebration}"] svg`));
    pendingCelebration = null;
  }
}

// --- Hoja: crear / editar meta ---
let goalSheet;
let editing = null;
function openGoalSheet(goal = null) {
  editing = goal;
  goalSheet ??= createSheet(`
    <form id="goal-form" class="space-y-3" novalidate>
      <h3 class="font-display text-xl font-bold mb-2" id="gf-title"></h3>
      <label class="field"><span>Nombre</span><input id="gf-name" class="input" maxlength="80" placeholder="Ej: Viaje a Brasil" autofocus /></label>
      <div class="grid grid-cols-2 gap-3">
        <label class="field"><span>Objetivo</span><input id="gf-target" class="input" inputmode="decimal" placeholder="Ej: 60.000" /></label>
        <label class="field"><span>Ya ahorrado</span><input id="gf-saved" class="input" inputmode="decimal" placeholder="0" /></label>
        <label class="field"><span>Fecha límite (opcional)</span><input id="gf-deadline" type="date" class="input" /></label>
        <label class="field"><span>Aporte fijo / mes (opcional)</span><input id="gf-contribution" class="input" inputmode="decimal" placeholder="Automático" /></label>
      </div>
      <p class="muted text-xs">Si no ponés aporte fijo, VaultBase reparte tu ahorro disponible entre las metas automáticamente.</p>
      <p class="form-error" id="gf-error"></p>
      <div class="flex gap-3">
        <button type="button" class="btn btn-danger" id="gf-delete"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
        <button class="btn btn-primary flex-1" id="gf-save">Guardar</button>
      </div>
    </form>`, { label: "Meta" });
  const q = (s) => goalSheet.el.querySelector(s);
  if (!goalSheet.ready) {
    goalSheet.ready = true;
    q("#goal-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const target = parseMoney(q("#gf-target").value);
      const savedText = q("#gf-saved").value.trim();
      const saved = savedText ? parseMoney(savedText) : 0;
      const contribText = q("#gf-contribution").value.trim();
      const contribution = contribText ? parseMoney(contribText) : null;
      const name = q("#gf-name").value.trim();
      if (!name) return (q("#gf-error").textContent = "Ponele un nombre.");
      if (!target) return (q("#gf-error").textContent = "Escribí el monto objetivo.");
      if (saved === null || (contribText && contribution === null)) return (q("#gf-error").textContent = "Revisá los montos.");
      const body = { name, target_cents: target, saved_cents: saved, deadline: q("#gf-deadline").value || null,
                     monthly_contribution_cents: contribution };
      try {
        const res = await api(editing ? `/api/goals/${editing.id}` : "/api/goals", { method: editing ? "PATCH" : "POST", body });
        if (res.saved_cents >= res.target_cents && (!editing || editing.saved_cents < editing.target_cents)) pendingCelebration = res.id;
        toast(editing ? "Meta actualizada" : "Meta creada");
        goalSheet.close();
        notifyDataChanged();
      } catch (err) { q("#gf-error").textContent = err.message; }
    });
    q("#gf-delete").addEventListener("click", async () => {
      if (!(await confirmDialog("¿Borrar esta meta?"))) return;
      await api(`/api/goals/${editing.id}`, { method: "DELETE" });
      toast("Meta borrada");
      goalSheet.close();
      notifyDataChanged();
    });
  }
  const g = goal ?? {};
  q("#gf-title").textContent = goal ? "Editar meta" : "Nueva meta";
  q("#gf-name").value = g.name ?? "";
  q("#gf-target").value = goal ? centsToInput(g.target_cents) : "";
  q("#gf-saved").value = goal ? centsToInput(g.saved_cents) : "";
  q("#gf-deadline").value = g.deadline ?? "";
  q("#gf-contribution").value = g.monthly_contribution_cents != null ? centsToInput(g.monthly_contribution_cents) : "";
  q("#gf-delete").hidden = !goal;
  q("#gf-error").textContent = "";
  icons();
  goalSheet.open();
}

// --- Hoja: sumar ahorro a una meta ---
let savingSheet;
let savingGoal = null;
function openSavingSheet(goal) {
  savingGoal = goal;
  savingSheet ??= createSheet(`
    <form id="saving-form" novalidate>
      <h3 class="font-display text-xl font-bold mb-1">Sumar ahorro</h3>
      <p class="muted text-sm mb-2" id="sf-goal"></p>
      <input id="sf-amount" class="amount-input my-4" inputmode="decimal" placeholder="0" aria-label="Monto a sumar" autofocus />
      <div class="flex flex-wrap gap-2 justify-center mb-4" id="sf-quick"></div>
      <p class="form-error mb-2" id="sf-error"></p>
      <button class="btn btn-primary w-full">Sumar</button>
    </form>`, { label: "Sumar ahorro" });
  const q = (s) => savingSheet.el.querySelector(s);
  if (!savingSheet.ready) {
    savingSheet.ready = true;
    savingSheet.el.addEventListener("click", (e) => {
      const quick = e.target.closest("[data-quick]");
      if (quick) q("#sf-amount").value = centsToInput(Number(quick.dataset.quick));
    });
    q("#saving-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const amount = parseMoney(q("#sf-amount").value);
      if (!amount) return (q("#sf-error").textContent = "Escribí un monto válido.");
      const newSaved = savingGoal.saved_cents + amount;
      try {
        await api(`/api/goals/${savingGoal.id}`, { method: "PATCH", body: { saved_cents: newSaved } });
        if (newSaved >= savingGoal.target_cents) {
          pendingCelebration = savingGoal.id;
          toast(`¡Completaste "${savingGoal.name}"! 🎉`);
        } else {
          toast(`Sumaste ${money(amount)} a ${savingGoal.name}`);
        }
        savingSheet.close();
        notifyDataChanged();
      } catch (err) { q("#sf-error").textContent = err.message; }
    });
  }
  const p = projections[goal.id];
  const remaining = goal.target_cents - goal.saved_cents;
  q("#sf-goal").textContent = `${goal.name} · te faltan ${money(remaining)}`;
  q("#sf-amount").value = "";
  q("#sf-error").textContent = "";
  // Atajos: el aporte mensual sugerido y "lo que falta"
  const options = [p?.monthly_contribution_cents, remaining].filter((v, i, arr) => v > 0 && arr.indexOf(v) === i);
  q("#sf-quick").innerHTML = options.map((v) =>
    `<button type="button" class="chip" data-quick="${v}">${v === remaining ? "Lo que falta · " : "Aporte del mes · "}${money(v)}</button>`).join("");
  savingSheet.open();
}

// --- Hoja: el plan para llegar a la meta ---
// El backend calcula todo (/api/finance/goals/{id}/plan); acá solo lo dibujamos.
const TIP_ICON = {
  set_contribution: "lock", aguinaldo: "gift", cut: "scissors", subscriptions: "repeat", extend: "calendar-clock",
};
const isoMonth = (y, m) => `${y}-${String(m).padStart(2, "0")}-01`;
const shortMonth = (y, m) => new Date(y, m - 1, 1).toLocaleDateString("es-UY", { month: "short", year: "2-digit" });

// 1) La frase de arriba: qué querés y cuánto hay que juntar por mes
function planHeadline(plan, when) {
  const target = `<b>${money(plan.remaining_cents)}</b>`;
  if (plan.based_on === "deadline") {
    // La fecha exacta ("1 de diciembre de 2026"), no solo el mes: si vence el 1, hay que tenerlo antes
    const exact = new Date(plan.deadline + "T00:00").toLocaleDateString("es-UY", { day: "numeric", month: "long", year: "numeric" });
    return `Para juntar los ${target} que te faltan antes del <b>${exact}</b>, necesitás ahorrar:`;
  }
  if (plan.based_on === "suggested") return `No le pusiste fecha. Para juntar los ${target} que te faltan en un año (<b>${when}</b>), necesitás ahorrar:`;
  return `Te faltan ${target}. Al ritmo de hoy llegás en <b>${when}</b> ahorrando:`;
}

// 2) "¿Te alcanza?": lo que necesitás vs. lo que te sobra hoy para esta meta
function planCheck(plan) {
  const need = plan.monthly_cents;
  const have = plan.current_contribution_cents;
  const ok = plan.gap_cents === 0;
  const pct = need ? Math.min((have / need) * 100, 100) : 100;
  const shared = plan.other_goals
    ? `De los ${money(plan.monthly_savings_cents)} que te sobran por mes (sueldo menos gastos), a esta meta le toca esta parte porque también tenés ${plan.other_goals === 1 ? "otra meta" : `${plan.other_goals} metas más`}.`
    : "Es lo que te sobra por mes: lo que entra menos lo que gastás.";
  const late = !ok && plan.current_finish_year
    ? `<p class="muted text-xs mt-2">Si no cambiás nada y ahorrás solo eso, llegás recién en <b>${monthYear(isoMonth(plan.current_finish_year, plan.current_finish_month))}</b>.</p>`
    : !ok ? `<p class="muted text-xs mt-2">Hoy no te sobra plata para esta meta: con lo de ahora no llegarías.</p>` : "";
  return `
    <div class="card p-4 mt-5">
      <h4 class="font-display font-bold mb-3">¿Te alcanza?</h4>
      <div class="space-y-2 text-sm">
        <div class="flex justify-between gap-3"><span>Necesitás ahorrar</span><b class="tabular-nums">${money(need)} / mes</b></div>
        <div class="flex justify-between gap-3"><span>Hoy te sobra para esta meta</span><b class="tabular-nums text-primary">${money(have)} / mes</b></div>
      </div>
      <div class="bar mt-3" style="background:${ok ? "var(--surface-2)" : "var(--danger-soft)"}">
        <span data-fill="${pct}" style="background:${ok ? "var(--success)" : "var(--primary)"}"></span></div>
      <p class="muted text-xs mt-2">${shared}</p>
      <div class="mt-3 rounded-xl p-3 text-sm flex gap-2 items-center ${ok ? "bg-primary-soft" : "bg-danger-soft"}">
        <i data-lucide="${ok ? "circle-check" : "circle-alert"}" class="w-4 h-4 shrink-0 ${ok ? "text-success" : "text-danger"}"></i>
        <span>${ok ? "<b>Te alcanza.</b> Solo hay que sostenerlo todos los meses."
                   : `<b>Te faltan ${money(plan.gap_cents)} por mes.</b> Abajo tenés ideas para conseguirlos.`}</span>
      </div>
      ${late}
    </div>`;
}

// 3) Ideas: cada una dice cuánto suma por mes, y al final si todas juntas alcanzan
function planIdeas(plan) {
  const ideas = plan.tips.filter((t) => t.kind !== "extend");
  const extend = plan.tips.find((t) => t.kind === "extend");
  if (!ideas.length && !extend) return "";
  const total = ideas.reduce((s, t) => s + (t.monthly_cents ?? 0), 0);
  const covers = total >= plan.gap_cents;
  const card = (t, i) => `
    <li class="card p-3 flex gap-3 items-start rise" style="animation-delay:${0.15 + i * 0.06}s">
      <span class="grid place-items-center w-9 h-9 rounded-xl bg-accent-soft text-accent shrink-0"><i data-lucide="${TIP_ICON[t.kind] ?? "lightbulb"}" class="w-4 h-4"></i></span>
      <div class="min-w-0 flex-1">
        <div class="font-medium text-sm">${esc(t.title)}</div>
        <div class="muted text-xs mt-0.5">${esc(t.detail)}</div>
        <div class="flex flex-wrap items-center gap-2 mt-2 empty:hidden">${
          t.monthly_cents ? `<span class="chip text-success whitespace-nowrap">Suma +${money(t.monthly_cents)} por mes</span>` : ""}${
          t.kind === "set_contribution" ? `<button class="btn btn-primary text-xs py-1.5" data-set-contribution="${t.amount_cents}">Aplicar</button>` : ""}</div>
      </div>
    </li>`;
  const summary = total ? `
    <div class="mt-3 rounded-xl p-3 text-sm ${covers ? "bg-primary-soft" : "bg-accent-soft"}">
      Si hacés todo esto juntás <b>+${money(total)} por mes</b>:
      ${covers ? `<b class="text-success">alcanza</b> para llegar a tiempo.` : `todavía faltarían <b>${money(plan.gap_cents - total)}</b> por mes.`}
    </div>` : "";
  return `
    ${ideas.length ? `
      <h4 class="font-display font-bold mt-6 mb-1">Ideas para conseguir los ${money(plan.gap_cents)} que faltan</h4>
      <p class="muted text-xs mb-3">Cada una muestra cuánto te suma por mes. Podés combinarlas.</p>
      <ul class="space-y-2">${ideas.map(card).join("")}</ul>${summary}` : ""}
    ${extend ? `
      <h4 class="font-display font-bold mt-6 mb-3">${ideas.length ? "O si no querés cambiar nada…" : "Otra opción"}</h4>
      <ul>${card(extend, ideas.length)}</ul>` : ""}`;
}

function planHTML(plan) {
  const when = monthYear(isoMonth(plan.finish_year, plan.finish_month));
  const steps = [
    `Cuando cobres, separá <b>${money(plan.monthly_cents)}</b> antes de gastar en otra cosa.`,
    "Guardalo aparte (otra cuenta o caja de ahorro) para no tocarlo sin querer.",
    "Cada mes tocá <b>Sumar ahorro</b> acá: así ves si vas al día con los hitos.",
  ];
  const milestones = plan.milestones.map((m, i) => `
    <li class="grid grid-cols-[3.5rem_1fr_auto] gap-3 items-center rise" style="animation-delay:${0.2 + i * 0.04}s">
      <span class="text-xs muted capitalize">${shortMonth(m.year, m.month)}</span>
      <div class="bar"><span data-fill="${m.progress_pct}" style="background:${m.is_last ? "var(--success)" : "var(--primary)"}"></span></div>
      <span class="text-xs tabular-nums text-right">${money(m.saved_cents)}${m.aguinaldo_cents ? ` <i data-lucide="gift" class="inline w-3 h-3 text-accent" aria-label="mes de aguinaldo"></i>` : ""}${m.is_last ? ` <i data-lucide="flag" class="inline w-3 h-3 text-success"></i>` : ""}</span>
    </li>`).join("");

  return `
    <p class="muted text-sm">Plan · ${esc(plan.name)}</p>
    <p class="text-sm mt-3">${planHeadline(plan, when)}</p>
    <div class="mt-1 flex items-baseline gap-2 flex-wrap">
      <span class="font-display text-4xl font-bold text-primary" id="plan-monthly">$ 0</span><span class="muted">por mes</span>
    </div>
    <div class="flex gap-2 mt-2 flex-wrap">
      <span class="chip">o ${money(plan.weekly_cents)} por semana</span>
      <span class="chip">o ${money(plan.daily_cents)} por día</span>
    </div>
    ${planCheck(plan)}
    ${planIdeas(plan)}
    <h4 class="font-display font-bold mt-6 mb-3">Tus pasos</h4>
    <ol class="space-y-2 text-sm">${steps.map((s, i) => `
      <li class="flex gap-3"><span class="grid place-items-center w-6 h-6 rounded-full bg-primary-soft text-primary text-xs font-bold shrink-0">${i + 1}</span><span>${s}</span></li>`).join("")}</ol>
    <h4 class="font-display font-bold mt-6 mb-1">Hitos</h4>
    <p class="muted text-xs mb-3">Lo que deberías tener ahorrado a fin de cada mes${plan.milestones.some((m) => m.aguinaldo_cents) ? " · <i data-lucide=\"gift\" class=\"inline w-3 h-3 text-accent\"></i> = cobrás aguinaldo" : ""}.</p>
    <ul class="space-y-2.5">${milestones}</ul>
    <button class="btn btn-ghost w-full mt-6" data-close>Cerrar</button>`;
}

let planSheet;
let planGoal = null;
async function openPlanSheet(goal) {
  planGoal = goal;
  planSheet ??= createSheet(`<div id="plan-body" class="min-h-40"></div>`, { label: "Plan de la meta" });
  if (!planSheet.ready) {
    planSheet.ready = true;
    planSheet.el.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-set-contribution]");
      if (!btn) return;
      btn.disabled = true;
      await api(`/api/goals/${planGoal.id}`, { method: "PATCH", body: { monthly_contribution_cents: Number(btn.dataset.setContribution) } });
      toast(`Aporte fijo para ${planGoal.name}`);
      notifyDataChanged();
      openPlanSheet(planGoal);  // redibuja el plan con el aporte nuevo
    });
  }
  const body = planSheet.el.querySelector("#plan-body");
  if (!planSheet.el.classList.contains("sheet-open")) body.innerHTML = `<p class="muted text-sm">Armando tu plan…</p>`;
  planSheet.open();
  const plan = await api(`/api/finance/goals/${goal.id}/plan`);
  body.innerHTML = planHTML(plan);
  icons();
  fillBars(body);
  countUp(body.querySelector("#plan-monthly"), plan.monthly_cents);
}

function init() {
  $("add-goal").addEventListener("click", () => openGoalSheet());
  document.addEventListener("click", (e) => {
    const find = (attr) => goals.find((g) => g.id === Number(e.target.closest(`[${attr}]`)?.getAttribute(attr)));
    if (e.target.closest("[data-plan]")) openPlanSheet(find("data-plan"));
    if (e.target.closest("[data-add-saving]")) openSavingSheet(find("data-add-saving"));
    if (e.target.closest("[data-edit]")) openGoalSheet(find("data-edit"));
    if (e.target.closest("[data-new]")) openGoalSheet();
  });
  onDataChanged(load);
  load();
}

if (mountShell()) init();
