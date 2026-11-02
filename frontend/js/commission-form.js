// commission-form.js · Hoja para anotar la comisión de una semana.
//
// Como no sabés el monto exacto hasta el recibo, se anota un RANGO
// ("entre $ 14.000 y $ 19.000"). Cuando llega el recibo, marcás "ya sé el
// monto exacto" y ese número reemplaza al rango en todos los cálculos.

import { api } from "./api.js";
import { centsToInput, money, parseDate, parseMoney, shortDate, toISO } from "./format.js";
import { confirmDialog, createSheet, notifyDataChanged, toast } from "./ui.js";

let sheet;
let editing = null;
let payDay = 30;  // día de cobro del sueldo (para decir cuándo se cobra cada semana)

const template = `
  <form id="commission-form" novalidate>
    <h3 class="font-display text-xl font-bold mb-1" id="cf-title">Comisión de la semana</h3>
    <p class="muted text-sm mb-4">Si todavía no sabés cuánto vas a cobrar, poné un rango: la app usa el mínimo para planificar.</p>
    <label class="field mb-1"><span>Semana (cualquier día de esa semana)</span>
      <input id="cf-week" type="date" class="input" /></label>
    <p class="muted text-xs mb-3" id="cf-week-info"></p>
    <label class="flex items-center gap-2 text-sm cursor-pointer mb-3">
      <input type="checkbox" id="cf-exact" style="accent-color:var(--primary)" class="w-4 h-4" />
      Ya sé el monto exacto (me llegó el recibo)
    </label>
    <div class="grid grid-cols-2 gap-3" id="cf-range">
      <label class="field"><span>Como mínimo</span><input id="cf-min" class="input" inputmode="decimal" placeholder="Ej: 14.000" /></label>
      <label class="field"><span>Como máximo</span><input id="cf-max" class="input" inputmode="decimal" placeholder="Ej: 19.000" /></label>
    </div>
    <label class="field" id="cf-actual-wrap" hidden><span>Monto real</span>
      <input id="cf-actual" class="input" inputmode="decimal" placeholder="Ej: 16.500" /></label>
    <label class="flex items-start gap-2 text-sm cursor-pointer mt-3">
      <input type="checkbox" id="cf-nominal" style="accent-color:var(--primary)" class="w-4 h-4 mt-0.5" />
      <span>Son montos <b>nominales</b> (como en el recibo, antes de aportes)
        <span class="muted text-xs block">Descontamos BPS 15% + FONASA 4,5% + FRL 0,1% y guardamos lo que te entra en mano.</span></span>
    </label>
    <p class="text-xs text-primary mt-1" id="cf-net"></p>
    <label class="field mt-3"><span>Nota (opcional)</span>
      <input id="cf-note" class="input" maxlength="120" placeholder="Ej: 356% de la meta" /></label>
    <p class="form-error my-3" id="cf-error"></p>
    <div class="flex gap-3">
      <button type="button" class="btn btn-danger" id="cf-delete" hidden><i data-lucide="trash-2" class="w-4 h-4"></i></button>
      <button type="submit" class="btn btn-primary flex-1" id="cf-save">Guardar</button>
    </div>
  </form>`;

const $ = (sel) => sheet.el.querySelector(sel);

// Aportes personales sobre las comisiones (los mismos que ves en el recibo):
// BPS 15% + FONASA 4,5% + FRL 0,1%. Ojo: FONASA puede ser otro % según tu
// situación (cónyuge, hijos); en ese caso el resultado es aproximado.
const NET_FACTOR = 1 - (0.15 + 0.045 + 0.001);
const toNet = (cents) => (cents == null ? null : Math.round(cents * NET_FACTOR));
const nominal = () => $("#cf-nominal").checked;

/** El lunes de la semana de una fecha. */
export function mondayOf(date) {
  const d = new Date(date);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return d;
}

/** Cuándo se cobra una semana: con el sueldo del mes en que termina (su domingo). */
export function payDateOf(weekStartISO, day = payDay) {
  const sunday = parseDate(weekStartISO);
  sunday.setDate(sunday.getDate() + 6);
  const last = new Date(sunday.getFullYear(), sunday.getMonth() + 1, 0).getDate();
  return toISO(new Date(sunday.getFullYear(), sunday.getMonth(), Math.min(day, last)));
}

function sync() {
  const exact = $("#cf-exact").checked;
  $("#cf-range").hidden = exact;
  $("#cf-actual-wrap").hidden = !exact;
  // Vista previa de lo que te entra en mano
  const nums = (exact ? [$("#cf-actual").value] : [$("#cf-min").value, $("#cf-max").value || $("#cf-min").value])
    .map(parseMoney);
  $("#cf-net").textContent = nominal() && nums.every((n) => n != null)
    ? `≈ ${nums.map((n) => money(toNet(n))).filter((v, i, a) => a.indexOf(v) === i).join(" – ")} en mano`
    : "";
  const value = $("#cf-week").value;
  if (value) {
    const monday = toISO(mondayOf(parseDate(value)));
    const sunday = parseDate(monday);
    sunday.setDate(sunday.getDate() + 6);
    $("#cf-week-info").textContent =
      `Semana del ${shortDate(monday)} al ${shortDate(toISO(sunday))} · se cobra el ${shortDate(payDateOf(monday))} con tu sueldo.`;
  }
}

function ensureSheet() {
  if (sheet) return;
  sheet = createSheet(template, { label: "Comisión" });
  $("#cf-exact").addEventListener("change", sync);
  $("#cf-week").addEventListener("change", sync);
  $("#cf-nominal").addEventListener("change", sync);
  ["#cf-min", "#cf-max", "#cf-actual"].forEach((id) => $(id).addEventListener("input", sync));
  $("#cf-delete").addEventListener("click", async () => {
    if (!(await confirmDialog("¿Borrar esta semana?"))) return;
    await api(`/api/commissions/${editing.id}`, { method: "DELETE" });
    toast("Semana borrada");
    sheet.close();
    notifyDataChanged();
  });
  $("#commission-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = (msg) => ($("#cf-error").textContent = msg);
    if (!$("#cf-week").value) return err("Elegí la semana.");
    const body = { week_start: toISO(mondayOf(parseDate($("#cf-week").value))), note: $("#cf-note").value.trim() || null };
    if ($("#cf-exact").checked) {
      let actual = parseMoney($("#cf-actual").value);
      if (actual === null) return err("Escribí el monto real.");
      if (nominal()) actual = toNet(actual);
      // Con el monto real, el rango ya no importa: lo dejamos igual al real
      Object.assign(body, { actual_cents: actual, min_cents: actual, max_cents: actual });
    } else {
      const min = parseMoney($("#cf-min").value);
      const maxText = $("#cf-max").value.trim();
      const max = maxText ? parseMoney(maxText) : min;  // sin máximo = monto fijo
      if (min === null || max === null) return err("Escribí al menos el mínimo.");
      if (min > max) return err("El mínimo no puede ser mayor que el máximo.");
      Object.assign(body, nominal() ? { min_cents: toNet(min), max_cents: toNet(max) } : { min_cents: min, max_cents: max },
        { actual_cents: null });
    }
    $("#cf-save").disabled = true;
    try {
      await api(editing ? `/api/commissions/${editing.id}` : "/api/commissions",
        { method: editing ? "PATCH" : "POST", body });
      toast(editing ? "Semana actualizada" : "Comisión anotada");
      sheet.close();
      notifyDataChanged();
    } catch (error) {
      err(error.message);
    } finally {
      $("#cf-save").disabled = false;
    }
  });
}

/** Abre la hoja. Sin comisión = semana nueva (por defecto, la semana pasada). */
export function openCommissionSheet(commission = null, { salaryPayDay = 30 } = {}) {
  ensureSheet();
  editing = commission;
  payDay = salaryPayDay;
  const c = commission ?? {};
  const lastWeek = mondayOf(new Date());
  lastWeek.setDate(lastWeek.getDate() - 7);
  $("#cf-title").textContent = commission ? "Editar semana" : "Comisión de la semana";
  $("#cf-week").value = c.week_start ?? toISO(lastWeek);
  $("#cf-exact").checked = c.actual_cents != null;
  $("#cf-min").value = commission ? centsToInput(c.min_cents) : "";
  $("#cf-max").value = commission ? centsToInput(c.max_cents) : "";
  $("#cf-actual").value = c.actual_cents != null ? centsToInput(c.actual_cents) : "";
  $("#cf-note").value = c.note ?? "";
  // Semana nueva: lo normal es saber el nominal. Al editar, lo guardado ya está en mano.
  $("#cf-nominal").checked = !commission;
  $("#cf-delete").hidden = !commission;
  $("#cf-error").textContent = "";
  sync();
  sheet.open();
}

/** Cómo se muestra el monto de una semana en la lista. */
export const commissionAmount = (c) => c.actual_cents != null
  ? money(c.actual_cents)
  : c.min_cents === c.max_cents ? money(c.min_cents) : `${money(c.min_cents)} – ${money(c.max_cents)}`;
