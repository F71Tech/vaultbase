// simulador.js · "Si compro X por $Y": compara formas de pago y recomienda.

import { api } from "../api.js";
import { centsToInput, money, moneyExact, parseMoney } from "../format.js";
import { PRIORITY } from "../labels.js";
import { mountShell } from "../shell.js";
import { confirmDialog, createSheet, esc, icons, notifyDataChanged, onDataChanged, toast } from "../ui.js";

const $ = (id) => document.getElementById(id);
const FREE_OPTIONS = [3, 6, 10, 12, 18, 24];
const state = { currency: "UYU", free: new Set([3, 6, 12]), interest: [] };
let wishes = [];

// --- Opciones de cuotas ---
function renderInstallmentOptions() {
  $("free-installments").innerHTML = FREE_OPTIONS.map((n) =>
    `<button type="button" class="chip" data-free="${n}" aria-pressed="${state.free.has(n)}">${n} sin interés</button>`).join("");
  $("interest-rows").innerHTML = state.interest.map((row, i) => `
    <div class="flex items-center gap-2">
      <input class="input py-2 px-2 text-center" style="width:4.5rem" type="number" min="2" max="60" value="${row.count}" data-row="${i}" data-field="count" aria-label="Cuotas" />
      <span class="muted text-sm shrink-0">cuotas al</span>
      <input class="input py-2 px-2 text-center" style="width:5rem" type="number" min="0" max="500" step="0.1" value="${row.rate}" data-row="${i}" data-field="rate" aria-label="Tasa anual" />
      <span class="muted text-sm shrink-0">% anual</span>
      <button type="button" class="btn-icon btn muted" data-remove="${i}" aria-label="Quitar"><i data-lucide="x" class="w-4 h-4"></i></button>
    </div>`).join("");
  document.querySelectorAll("[data-currency]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.currency === state.currency));
  icons();
}

// --- Resultado ---
const purchaseText = (s) => {
  if (s.purchase_in_months === 0) return "Hoy";
  const text = new Date(s.purchase_date + "T00:00").toLocaleDateString("es-UY", { month: "long", year: "numeric" });
  return text.charAt(0).toUpperCase() + text.slice(1);  // "diciembre de 2026" -> "Diciembre de 2026"
};

function strategyCard(s, savings, index) {
  // Barra: cuánto del ahorro mensual se come la cuota del primer mes
  const share = savings > 0 ? (s.monthly_payment_cents / savings) * 100 : 100;
  const over = share > 100;
  // Las metas ya cumplidas (0 meses sin compra) no se pueden atrasar: no las mostramos
  const goalDelays = s.goal_delays.filter((d) => d.months_without_purchase !== 0);
  const delays = goalDelays.length ? goalDelays.map((d) => `
      <li class="flex justify-between gap-2"><span class="truncate">${esc(d.name)}</span>
        <span class="${d.delay_months ? "text-accent" : "text-success"} shrink-0">${
          d.delay_months == null ? "no se alcanza" : d.delay_months === 0 ? "sin atraso" : `+${d.delay_months} ${d.delay_months === 1 ? "mes" : "meses"}`}</span></li>`).join("")
    : `<li class="muted">No tenés metas en curso.</li>`;
  return `
  <article class="card p-5 rise ${s.recommended ? "glow-border" : ""}" style="animation-delay:${index * 0.07}s">
    ${s.recommended ? `<span class="chip text-primary mb-2" style="border-color:var(--primary)"><i data-lucide="star" class="w-3.5 h-3.5"></i>Recomendada</span>`
      : s.negative_months ? `<span class="chip text-danger mb-2">Te deja en negativo ${s.negative_months} mes${s.negative_months > 1 ? "es" : ""}</span>` : ""}
    <h3 class="font-display font-semibold text-lg mb-4">${esc(s.label)}</h3>
    <dl class="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
      <div><dt class="muted">${s.key === "wait_aguinaldo" ? "Sale de tu ahorro" : "Pagás por mes"}</dt><dd class="font-display text-xl font-bold">${money(s.monthly_payment_cents)}</dd></div>
      <div><dt class="muted">Lo tenés</dt><dd class="font-display text-xl font-bold">${purchaseText(s)}</dd></div>
      <div><dt class="muted">Total</dt><dd class="font-semibold">${money(s.total_cost_cents)}</dd></div>
      <div><dt class="muted">Costo extra</dt><dd class="font-semibold ${s.extra_cost_cents ? "text-danger" : "text-success"}">${s.extra_cost_cents ? money(s.extra_cost_cents) : "$ 0"}</dd></div>
    </dl>
    <div class="mt-4">
      <div class="flex justify-between text-xs muted mb-1.5"><span>Del ahorro de ese mes</span><span class="${over ? "text-danger" : ""}">${Math.round(share)}%</span></div>
      <div class="bar"><span data-fill="${Math.min(share, 100)}" style="background:${over ? "var(--danger)" : "var(--primary)"}"></span></div>
    </div>
    <div class="mt-4 text-sm"><div class="muted mb-1">Tus metas</div><ul class="space-y-1">${delays}</ul></div>
    <div class="muted text-xs mt-4">Balance del año después: <b class="${s.year_balance_after_cents < 0 ? "text-danger" : ""}">${money(s.year_balance_after_cents)}</b></div>
  </article>`;
}

function renderResult(result, title) {
  const ordered = [...result.strategies].sort((a, b) => b.recommended - a.recommended);
  const best = ordered[0];
  $("results").innerHTML = `
    <div class="card p-5 rise glow-border">
      <div class="flex gap-4 items-start">
        <span class="icon-badge bg-primary-soft text-primary" style="width:48px;height:48px"><i data-lucide="lightbulb"></i></span>
        <div class="min-w-0">
          <div class="muted text-sm">${esc(title)} · ${money(result.price_cents)}</div>
          <p class="font-display text-lg md:text-xl font-semibold leading-snug mt-1">${esc(result.recommendation)}</p>
          <div class="muted text-sm mt-2">Tu ahorro posible: <b>${money(result.monthly_savings_cents)}</b>/mes</div>
        </div>
      </div>
    </div>
    <div class="grid md:grid-cols-2 gap-4">${ordered.map((s, i) => strategyCard(s, result.monthly_savings_cents, i + 1)).join("")}</div>`;
  icons();
  requestAnimationFrame(() => setTimeout(() => document.querySelectorAll("#results [data-fill]").forEach((b) => (b.style.width = `${b.dataset.fill}%`)), 150));
  if (best && innerWidth < 1024) $("results").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function simulate() {
  const price = parseMoney($("sim-price").value);
  if (!price) {
    $("sim-error").textContent = "Escribí el precio (ej: 45.000).";
    $("sim-price").focus();
    return;
  }
  $("sim-error").textContent = "";
  const installments = [
    ...[...state.free].sort((a, b) => a - b).map((count) => ({ count, annual_rate_pct: 0 })),
    ...state.interest.filter((r) => r.count >= 2 && r.rate > 0).map((r) => ({ count: Number(r.count), annual_rate_pct: Number(r.rate) })),
  ];
  $("sim-run").disabled = true;
  try {
    const result = await api("/api/finance/simulate", {
      method: "POST", body: { cost_cents: price, currency: state.currency, installments },
    });
    renderResult(result, $("sim-name").value.trim() || "Tu compra");
  } catch (err) {
    $("sim-error").textContent = err.message;
  } finally {
    $("sim-run").disabled = false;
  }
}

// --- Lista de deseos ---
const PRIORITY_STYLE = { high: "text-danger", medium: "text-accent", low: "muted" };
async function loadWishes() {
  wishes = await api("/api/wishlist");
  const order = { high: 0, medium: 1, low: 2 };
  wishes.sort((a, b) => order[a.priority] - order[b.priority]);
  $("wish-total").textContent = wishes.length ? `${wishes.length} ${wishes.length === 1 ? "cosa" : "cosas"}` : "";
  $("wish-list").innerHTML = wishes.length ? wishes.map((w) => `
    <div class="card p-4 card-hover" style="box-shadow:none">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0"><div class="font-semibold truncate">${esc(w.name)}</div>
          <div class="font-display text-lg font-bold">${moneyExact(w.cost_cents, w.currency)}</div></div>
        <span class="chip ${PRIORITY_STYLE[w.priority]} shrink-0">${PRIORITY[w.priority]}</span>
      </div>
      ${w.notes ? `<p class="muted text-xs mt-1 truncate">${esc(w.notes)}</p>` : ""}
      <div class="flex gap-2 mt-3">
        <button class="btn btn-primary text-sm flex-1 py-2" data-sim-wish="${w.id}"><i data-lucide="sparkles" class="w-4 h-4"></i>Simular</button>
        <button class="btn btn-ghost text-sm py-2" data-edit-wish="${w.id}" aria-label="Editar"><i data-lucide="pencil" class="w-4 h-4"></i></button>
      </div>
    </div>`).join("")
    : `<p class="muted text-sm sm:col-span-2 lg:col-span-3">Guardá acá lo que te gustaría comprar (con el botón <i data-lucide="bookmark-plus" class="w-4 h-4 inline"></i> del formulario) y simulalo cuando quieras.</p>`;
  icons();
}

let wishSheet;
let editingWish = null;
let wishCurrency = "UYU";
function openWishSheet(wish = null, prefill = {}) {
  editingWish = wish;
  wishSheet ??= createSheet(`
    <form id="wish-form" class="space-y-3" novalidate>
      <div class="flex items-center justify-between">
        <h3 class="font-display text-xl font-bold" id="wf-title"></h3>
        <div class="segmented" role="group" aria-label="Moneda">
          <button type="button" data-wcurrency="UYU">$U</button><button type="button" data-wcurrency="USD">US$</button>
        </div>
      </div>
      <label class="field"><span>Qué es</span><input id="wf-name" class="input" maxlength="80" autofocus /></label>
      <div class="grid grid-cols-2 gap-3">
        <label class="field"><span>Precio</span><input id="wf-cost" class="input" inputmode="decimal" /></label>
        <label class="field"><span>Prioridad</span><select id="wf-priority" class="input">
          ${Object.entries(PRIORITY).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></label>
      </div>
      <label class="field"><span>Notas (opcional)</span><input id="wf-notes" class="input" maxlength="200" placeholder="Ej: esperar al Black Friday" /></label>
      <p class="form-error" id="wf-error"></p>
      <div class="flex gap-3">
        <button type="button" class="btn btn-danger" id="wf-delete"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
        <button class="btn btn-primary flex-1">Guardar</button>
      </div>
    </form>`, { label: "Compra deseada" });
  const q = (s) => wishSheet.el.querySelector(s);
  const syncCur = () => wishSheet.el.querySelectorAll("[data-wcurrency]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.wcurrency === wishCurrency));
  if (!wishSheet.ready) {
    wishSheet.ready = true;
    wishSheet.el.addEventListener("click", (e) => {
      const c = e.target.closest("[data-wcurrency]");
      if (c) { wishCurrency = c.dataset.wcurrency; syncCur(); }
    });
    q("#wish-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = q("#wf-name").value.trim();
      const cost = parseMoney(q("#wf-cost").value);
      if (!name) return (q("#wf-error").textContent = "¿Qué es?");
      if (!cost) return (q("#wf-error").textContent = "Escribí el precio.");
      const body = { name, cost_cents: cost, currency: wishCurrency, priority: q("#wf-priority").value,
                     notes: q("#wf-notes").value.trim() || null };
      try {
        await api(editingWish ? `/api/wishlist/${editingWish.id}` : "/api/wishlist", { method: editingWish ? "PATCH" : "POST", body });
        toast(editingWish ? "Guardado" : "Agregado a tu lista");
        wishSheet.close();
        notifyDataChanged();
      } catch (err) { q("#wf-error").textContent = err.message; }
    });
    q("#wf-delete").addEventListener("click", async () => {
      if (!(await confirmDialog(`¿Sacar "${editingWish.name}" de tu lista?`, { confirmText: "Sacar" }))) return;
      await api(`/api/wishlist/${editingWish.id}`, { method: "DELETE" });
      toast("Sacado de tu lista");
      wishSheet.close();
      notifyDataChanged();
    });
  }
  const w = wish ?? prefill;
  wishCurrency = w.currency ?? "UYU";
  q("#wf-title").textContent = wish ? "Editar deseo" : "Guardar en mi lista";
  q("#wf-name").value = w.name ?? "";
  q("#wf-cost").value = w.cost_cents ? centsToInput(w.cost_cents) : "";
  q("#wf-priority").value = w.priority ?? "medium";
  q("#wf-notes").value = w.notes ?? "";
  q("#wf-delete").hidden = !wish;
  q("#wf-error").textContent = "";
  syncCur();
  icons();
  wishSheet.open();
}

function init() {
  renderInstallmentOptions();
  $("sim-form").addEventListener("submit", (e) => { e.preventDefault(); simulate(); });
  $("add-installment").addEventListener("click", () => {
    state.interest.push({ count: 12, rate: 45 });
    renderInstallmentOptions();
  });
  $("save-wish").addEventListener("click", () => openWishSheet(null, {
    name: $("sim-name").value.trim(), cost_cents: parseMoney($("sim-price").value), currency: state.currency,
  }));

  document.addEventListener("click", (e) => {
    const t = e.target;
    const free = t.closest("[data-free]");
    const cur = t.closest("#sim-form [data-currency]");
    const remove = t.closest("[data-remove]");
    const simWish = t.closest("[data-sim-wish]");
    const editWish = t.closest("[data-edit-wish]");
    if (free) {
      const n = Number(free.dataset.free);
      state.free.has(n) ? state.free.delete(n) : state.free.add(n);
      renderInstallmentOptions();
    }
    if (cur) { state.currency = cur.dataset.currency; renderInstallmentOptions(); }
    if (remove) { state.interest.splice(Number(remove.dataset.remove), 1); renderInstallmentOptions(); }
    if (simWish) {
      // Carga el deseo en el formulario y simula
      const w = wishes.find((x) => x.id === Number(simWish.dataset.simWish));
      $("sim-name").value = w.name;
      $("sim-price").value = centsToInput(w.cost_cents);
      state.currency = w.currency;
      renderInstallmentOptions();
      simulate();
      scrollTo({ top: 0, behavior: "smooth" });
    }
    if (editWish) openWishSheet(wishes.find((x) => x.id === Number(editWish.dataset.editWish)));
  });
  $("interest-rows").addEventListener("input", (e) => {
    const { row, field } = e.target.dataset;
    if (row !== undefined) state.interest[Number(row)][field] = e.target.value;
  });
  onDataChanged(loadWishes);
  loadWishes();

  // Si venimos con ?wish=ID (por ejemplo desde otra pantalla), simulamos ese deseo
  const wishParam = new URLSearchParams(location.search).get("wish");
  if (wishParam) setTimeout(() => document.querySelector(`[data-sim-wish="${wishParam}"]`)?.click(), 600);
}

if (mountShell()) init();
