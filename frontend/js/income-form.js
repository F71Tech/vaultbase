// income-form.js · Hoja para cargar o editar un ingreso.

import { api } from "./api.js";
import { centsToInput, parseMoney, shortDate, toISO, todayISO } from "./format.js";
import { FREQUENCY } from "./labels.js";
import { confirmDialog, createSheet, notifyDataChanged, toast } from "./ui.js";

let sheet;
let editing = null;
let currency = "UYU";

const template = `
  <form id="income-form" novalidate>
    <div class="flex items-center justify-between mb-4">
      <h3 class="font-display text-xl font-bold" id="if-title">Nuevo ingreso</h3>
      <div class="segmented" role="group" aria-label="Moneda">
        <button type="button" data-currency="UYU" aria-pressed="true">$U</button>
        <button type="button" data-currency="USD" aria-pressed="false">US$</button>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-3">
      <label class="field col-span-2"><span>¿De dónde viene?</span>
        <input id="if-source" class="input" maxlength="80" placeholder="Ej: Sueldo, Freelance, Alquiler" autofocus /></label>
      <label class="field"><span>Monto</span>
        <input id="if-amount" class="input" inputmode="decimal" placeholder="Ej: 45.000" /></label>
      <label class="field"><span>Frecuencia</span>
        <select id="if-frequency" class="input">
          ${Object.entries(FREQUENCY).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}
        </select></label>
      <label class="field"><span id="if-start-label">Desde</span><input id="if-start" type="date" class="input" /></label>
      <label class="field" id="if-end-wrap"><span>Hasta (vacío = sigue)</span><input id="if-end" type="date" class="input" /></label>
    </div>
    <p id="if-onetime-warn" class="mt-3 rounded-xl bg-danger-soft p-3 text-xs flex gap-2 items-start" hidden>
      <i data-lucide="circle-alert" class="w-4 h-4 text-danger shrink-0"></i>
      <span><b>"Única vez" significa que no se repite:</b> la app va a dejar de contar este ingreso en los próximos meses
        (y tu plata y tus metas van a dar mucho menos). Si tu sueldo varía, dejalo <b>Mensual</b> con el sueldo base
        y anotá las comisiones aparte.</span>
    </p>
    <label class="flex items-start gap-2 text-sm cursor-pointer mt-3">
      <input type="checkbox" id="if-food-only" style="accent-color:var(--accent)" class="w-4 h-4 mt-0.5" />
      <span>Es un <b>ticket de alimentación</b> (otra tarjeta, solo para comida)
        <span class="muted text-xs block">No se suma a tu plata libre: paga primero tus gastos de comida.</span></span>
    </label>
    <!-- Solo para ingresos mensuales: QUÉ DÍA entra la plata (lo usa "Tu plata hoy") -->
    <div id="if-monthly" class="mt-3 space-y-3">
      <label class="field"><span>Día de cobro</span>
        <input id="if-pay-day" class="input" type="number" min="1" max="31" inputmode="numeric" placeholder="1" /></label>
      <div id="if-salary-extras" class="space-y-3">
      <label class="flex items-center gap-2 text-sm cursor-pointer">
        <input type="checkbox" id="if-has-advance" style="accent-color:var(--primary)" class="w-4 h-4" />
        Cobro un adelanto fijo antes
      </label>
      <div id="if-advance" class="grid grid-cols-2 gap-3" hidden>
        <label class="field"><span>Monto del adelanto</span>
          <input id="if-advance-amount" class="input" inputmode="decimal" placeholder="Ej: 15.000" /></label>
        <label class="field"><span>Día del adelanto</span>
          <input id="if-advance-day" class="input" type="number" min="1" max="31" inputmode="numeric" placeholder="15" /></label>
        <p class="muted text-xs col-span-2">El adelanto es <b>parte</b> del monto de arriba: ese día entra el adelanto y el día de cobro, el resto.
          Si es plata extra (no sale de tu sueldo), cargalo como otro ingreso mensual con su propio día.</p>
      </div>
      <label class="flex items-center gap-2 text-sm cursor-pointer">
        <input type="checkbox" id="if-has-commissions" style="accent-color:var(--primary)" class="w-4 h-4" />
        Cobro comisiones semanales (sueldo variable)
      </label>
      <div id="if-commissions" class="space-y-2" hidden>
        <label class="field"><span>Bono mínimo por semana, en mano (si no llegás a la meta)</span>
          <input id="if-floor" class="input" inputmode="decimal" placeholder="Ej: 2.412 (0 si no tenés)" /></label>
        <p class="muted text-xs">En mano ≈ 80% del nominal (BPS, FONASA y FRL se llevan ~19,6%): un bono de $ 3.000 nominal son unos $ 2.412.</p>
        <p class="muted text-xs">Importante: en <b>Monto</b> poné solo lo que te entra de <b>sueldo base</b> (sin comisiones), sumando el adelanto.
          Las comisiones las anotás cada semana en <b>Movimientos → Ingresos → Comisiones</b> (con un rango si no sabés el monto exacto).</p>
      </div>
      </div>
    </div>
    <p class="form-error my-3" id="if-error"></p>
    <div class="flex gap-3">
      <button type="button" class="btn btn-danger" id="if-delete" hidden><i data-lucide="trash-2" class="w-4 h-4"></i></button>
      <button type="submit" class="btn btn-primary flex-1" id="if-save">Guardar</button>
    </div>
  </form>`;

const $ = (sel) => sheet.el.querySelector(sel);

function syncFields() {
  const oneTime = $("#if-frequency").value === "one_time";
  $("#if-end-wrap").hidden = oneTime;
  $("#if-start-label").textContent = oneTime ? "Fecha de cobro" : "Desde";
  $("#if-monthly").hidden = $("#if-frequency").value !== "monthly";
  $("#if-advance").hidden = !$("#if-has-advance").checked;
  $("#if-commissions").hidden = !$("#if-has-commissions").checked;
  $("#if-salary-extras").hidden = $("#if-food-only").checked;  // un ticket no tiene adelanto ni comisiones
  $("#if-onetime-warn").hidden = !(editing && editing.frequency !== "one_time" && oneTime);
  sheet.el.querySelectorAll("[data-currency]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.currency === currency));
}

/** El último día de cobro de un ingreso mensual (hoy o antes). Ej: cobra el 30 -> 30/10 si hoy es 2/11. */
function lastPayDate(income) {
  const today = new Date();
  const payDay = income.pay_day ?? 1;
  const onDay = (y, m) => new Date(y, m, Math.min(payDay, new Date(y, m + 1, 0).getDate()));
  let date = onDay(today.getFullYear(), today.getMonth());
  if (date > today) date = onDay(today.getFullYear(), today.getMonth() - 1);
  return toISO(date);
}

function ensureSheet() {
  if (sheet) return;
  sheet = createSheet(template, { label: "Ingreso" });
  sheet.el.addEventListener("click", (e) => {
    const cur = e.target.closest("[data-currency]");
    if (cur) { currency = cur.dataset.currency; syncFields(); }
  });
  $("#if-frequency").addEventListener("change", () => {
    // Pasar un ingreso que se repetía a "única vez": la fecha tiene que ser la
    // del cobro (no el día en que empezó, que puede ser de hace meses)
    if (editing && editing.frequency !== "one_time" && $("#if-frequency").value === "one_time") {
      $("#if-start").value = lastPayDate(editing);
    }
    syncFields();
  });
  $("#if-has-advance").addEventListener("change", syncFields);
  $("#if-has-commissions").addEventListener("change", syncFields);
  $("#if-food-only").addEventListener("change", () => {
    if ($("#if-food-only").checked && !$("#if-source").value.trim()) $("#if-source").value = "Ticket alimentación";
    syncFields();
  });
  $("#if-delete").addEventListener("click", async () => {
    if (!(await confirmDialog("¿Borrar este ingreso?"))) return;
    await api(`/api/incomes/${editing.id}`, { method: "DELETE" });
    toast("Ingreso borrado");
    sheet.close();
    notifyDataChanged();
  });
  $("#income-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const amount = parseMoney($("#if-amount").value);
    const source = $("#if-source").value.trim();
    if (!source) return ($("#if-error").textContent = "Poné un nombre (ej: Sueldo).");
    if (!amount) return ($("#if-error").textContent = "Escribí un monto válido.");
    const frequency = $("#if-frequency").value;
    const body = {
      source, amount_cents: amount, currency, frequency,
      start_date: $("#if-start").value || todayISO(),
      end_date: frequency === "one_time" ? null : ($("#if-end").value || null),
      advance_cents: null, advance_day: null, commission_floor_cents: null,
      food_only: $("#if-food-only").checked,
    };
    const extras = !body.food_only;  // el ticket no tiene adelanto ni comisiones
    if (frequency === "monthly") {
      const day = (id, fallback) => Number($(id).value || fallback);
      body.pay_day = day("#if-pay-day", 1);
      if (!(body.pay_day >= 1 && body.pay_day <= 31)) return ($("#if-error").textContent = "El día de cobro va de 1 a 31.");
      if (extras && $("#if-has-advance").checked) {
        body.advance_cents = parseMoney($("#if-advance-amount").value);
        body.advance_day = day("#if-advance-day", 15);
        if (!body.advance_cents) return ($("#if-error").textContent = "Escribí el monto del adelanto.");
        if (body.advance_cents >= amount) return ($("#if-error").textContent = "El adelanto tiene que ser menor que el total del mes.");
        if (!(body.advance_day >= 1 && body.advance_day <= 31)) return ($("#if-error").textContent = "El día del adelanto va de 1 a 31.");
      }
      if (extras && $("#if-has-commissions").checked) {
        const floorText = $("#if-floor").value.trim();
        body.commission_floor_cents = floorText ? parseMoney(floorText) : 0;
        if (body.commission_floor_cents === null) return ($("#if-error").textContent = "Revisá el bono mínimo.");
      }
    }
    $("#if-save").disabled = true;
    try {
      await api(editing ? `/api/incomes/${editing.id}` : "/api/incomes",
        { method: editing ? "PATCH" : "POST", body });
      // Un cobro único solo aparece en la lista de SU mes: decimos cuál, para que no parezca perdido
      toast(frequency === "one_time"
        ? `Guardado como cobro único del ${shortDate(body.start_date)}`
        : editing ? "Ingreso actualizado" : "Ingreso guardado");
      sheet.close();
      notifyDataChanged();
    } catch (err) {
      $("#if-error").textContent = err.message;
    } finally {
      $("#if-save").disabled = false;
    }
  });
}

export function openIncomeSheet(income = null) {
  ensureSheet();
  editing = income;
  const i = income ?? {};
  currency = i.currency ?? "UYU";
  $("#if-title").textContent = income ? "Editar ingreso" : "Nuevo ingreso";
  $("#if-source").value = i.source ?? "";
  $("#if-amount").value = income ? centsToInput(i.amount_cents) : "";
  $("#if-frequency").value = i.frequency ?? "monthly";
  $("#if-start").value = i.start_date ?? todayISO();
  $("#if-end").value = i.end_date ?? "";
  $("#if-pay-day").value = i.pay_day ?? 1;
  $("#if-has-advance").checked = Boolean(i.advance_cents);
  $("#if-advance-amount").value = i.advance_cents ? centsToInput(i.advance_cents) : "";
  $("#if-advance-day").value = i.advance_day ?? 15;
  $("#if-has-commissions").checked = i.commission_floor_cents != null;
  $("#if-food-only").checked = Boolean(i.food_only);
  $("#if-floor").value = i.commission_floor_cents ? centsToInput(i.commission_floor_cents) : "";
  $("#if-delete").hidden = !income;
  $("#if-error").textContent = "";
  syncFields();
  sheet.open();
}
