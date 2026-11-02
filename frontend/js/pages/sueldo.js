// sueldo.js · Calculadora nominal ↔ líquido y aguinaldo, en vivo mientras escribís.

import { api } from "../api.js";
import { centsToInput, money, parseMoney, todayISO } from "../format.js";
import { mountShell } from "../shell.js";
import { countUp, icons, toast } from "../ui.js";

const $ = (id) => document.getElementById(id);
const state = { mode: "nominal", children: 0, disabled: 0, spouse: false, share: 100 };
let result = null;
let timer;

// Partes de la barra apilada: [clave en la respuesta, nombre, color]
const PARTS = [
  ["net_cents", "Líquido (lo que cobrás)", "var(--primary)"],
  ["pension_cents", "BPS · jubilación (15%)", "var(--cat-3)"],
  ["fonasa_cents", "FONASA (salud)", "var(--cat-4)"],
  ["frl_cents", "FRL (0,1%)", "var(--cat-7)"],
  ["irpf_cents", "IRPF", "var(--danger)"],
];
const pct = (rate) => `${(rate * 100).toLocaleString("es-UY", { maximumFractionDigits: 1 })}%`;

function render() {
  const m = result.monthly;
  const mainCents = state.mode === "nominal" ? m.net_cents : m.nominal_cents;
  const otherCents = state.mode === "nominal" ? m.nominal_cents : m.net_cents;
  countUp($("result-main"), mainCents);
  countUp($("result-other"), otherCents);

  // Barra apilada: primero en 0 y después al ancho real, para que "crezca"
  $("stack").innerHTML = PARTS.map(([key, , color]) => `<span style="background:${color}" data-w="${(m[key] / m.nominal_cents) * 100}"></span>`).join("");
  requestAnimationFrame(() => setTimeout(() => $("stack").querySelectorAll("span").forEach((s) => (s.style.width = `${s.dataset.w}%`)), 60));

  $("legend").innerHTML = PARTS.map(([key, label, color]) => `
    <li class="flex items-center justify-between gap-2">
      <span class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${color}"></span>
        ${label.replace("FONASA (salud)", `FONASA (${pct(m.fonasa_rate)})`)}</span>
      <span class="${key === "net_cents" ? "font-semibold" : "muted"}">${money(m[key])} · ${pct(m[key] / m.nominal_cents)}</span>
    </li>`).join("");

  $("irpf-detail").innerHTML = `
    <div class="flex justify-between"><span>Base del IRPF${m.irpf_base_cents !== m.nominal_cents ? " (nominal + 6%)" : ""}</span><b>${money(m.irpf_base_cents)}</b></div>
    <div class="flex justify-between"><span>Impuesto según la escala por franjas</span><b>${money(m.irpf_gross_cents)}</b></div>
    <div class="flex justify-between"><span>− Deducciones (aportes${state.children + state.disabled ? " + hijos" : ""}) × ${pct(m.deduction_rate)}</span><b>${money(m.irpf_deductions_cents)}</b></div>
    <div class="flex justify-between border-t pt-1" style="border-color:var(--border)"><span>IRPF del mes</span><b class="text-danger">${money(m.irpf_cents)}</b></div>
    ${m.irpf_cents === 0 ? `<p class="pt-1">Las deducciones cubren el impuesto (o el sueldo está bajo el mínimo de 7 BPC): no pagás IRPF.</p>` : ""}`;

  countUp($("ag-nominal"), result.aguinaldo.nominal_cents);
  countUp($("ag-contrib"), result.aguinaldo.contributions_cents);
  countUp($("ag-net"), result.aguinaldo.net_cents);
  countUp($("annual"), result.annual_net_cents);
  $("use-income").disabled = false;
  icons();
}

async function calculate() {
  const amount = parseMoney($("amount").value);
  $("error").textContent = "";
  if (!amount) { $("use-income").disabled = true; return; }
  try {
    result = await api("/api/salary/calculate", {
      method: "POST",
      body: {
        [state.mode === "nominal" ? "nominal_cents" : "net_cents"]: amount,
        children: state.children, disabled_children: state.disabled,
        spouse: state.spouse, children_share_pct: state.share,
      },
    });
    render();
  } catch (err) {
    $("error").textContent = err.message;
  }
}
// "Debounce": esperamos a que dejes de escribir 300 ms antes de calcular,
// así no mandamos un pedido por cada tecla.
const schedule = () => { clearTimeout(timer); timer = setTimeout(calculate, 300); };

function syncControls() {
  document.querySelectorAll("[data-mode]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.mode === state.mode));
  document.querySelectorAll("[data-share]").forEach((b) => b.setAttribute("aria-pressed", Number(b.dataset.share) === state.share));
  $("amount-label").textContent = state.mode === "nominal" ? "Sueldo nominal mensual" : "Líquido que querés cobrar por mes";
  $("result-label").textContent = state.mode === "nominal" ? "Cobrás (líquido)" : "Necesitás un nominal de";
  $("result-other-label").textContent = state.mode === "nominal" ? "Nominal" : "Líquido";
  $("children").textContent = state.children;
  $("disabled").textContent = state.disabled;
  $("spouse").setAttribute("aria-checked", state.spouse);
  $("share-row").hidden = state.children + state.disabled === 0;
}

// --- "Usar como mi ingreso": crea o actualiza el ingreso "Sueldo" ---
async function useAsIncome() {
  const m = result.monthly;
  const body = {
    source: "Sueldo", amount_cents: m.net_cents, currency: "UYU", frequency: "monthly",
    nominal_cents: m.nominal_cents, aguinaldo_cents: result.aguinaldo.net_cents,
  };
  // Buscamos tu sueldo actual: el que vino de la calculadora (tiene nominal) o,
  // si lo cargaste a mano, uno vigente llamado "Sueldo". Así no lo duplicamos.
  const incomes = await api("/api/incomes");
  const active = incomes.filter((i) => !i.end_date);
  const existing = active.find((i) => i.nominal_cents != null)
    ?? active.find((i) => i.source.trim().toLowerCase() === "sueldo");
  try {
    if (existing) {
      await api(`/api/incomes/${existing.id}`, { method: "PATCH", body });
      toast(`Actualizamos tu sueldo: ${money(m.net_cents)} líquido + aguinaldo`);
    } else {
      await api("/api/incomes", { method: "POST", body: { ...body, start_date: todayISO() } });
      toast(`Guardamos tu sueldo: ${money(m.net_cents)} líquido + aguinaldo`);
    }
  } catch (err) {
    toast(err.message, "error");
  }
}

async function init() {
  syncControls();
  document.addEventListener("click", (e) => {
    const mode = e.target.closest("[data-mode]");
    const step = e.target.closest("[data-step]");
    const share = e.target.closest("[data-share]");
    if (mode && mode.dataset.mode !== state.mode) {
      // Al cambiar de modo, dejamos en el campo el valor equivalente
      if (result) $("amount").value = centsToInput(mode.dataset.mode === "nominal" ? result.monthly.nominal_cents : result.monthly.net_cents);
      state.mode = mode.dataset.mode;
    }
    if (step) {
      const [key, delta] = step.dataset.step.split(":");
      state[key] = Math.min(Math.max(state[key] + Number(delta), 0), 10);
    }
    if (share) state.share = Number(share.dataset.share);
    if (e.target.closest("#spouse")) state.spouse = !state.spouse;
    if (mode || step || share || e.target.closest("#spouse")) { syncControls(); schedule(); }
  });
  $("amount").addEventListener("input", schedule);
  $("salary-form").addEventListener("submit", (e) => e.preventDefault());
  $("use-income").addEventListener("click", useAsIncome);

  // Valores oficiales que usa el backend (año y BPC)
  api("/api/salary/params").then((p) => {
    $("params-year").textContent = p.year;
    $("params-bpc").textContent = money(p.bpc_cents);
  }).catch(() => {});

  // Si ya tenés un sueldo cargado, arrancamos con ese nominal
  const incomes = await api("/api/incomes");
  const salary = incomes.find((i) => i.nominal_cents != null && !i.end_date);
  if (salary) {
    $("amount").value = centsToInput(salary.nominal_cents);
    calculate();
  }
}

if (mountShell()) init();
