// income-form.js · Hoja para cargar o editar un ingreso.

import { api } from "./api.js";
import { centsToInput, parseMoney, todayISO } from "./format.js";
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
  sheet.el.querySelectorAll("[data-currency]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.currency === currency));
}

function ensureSheet() {
  if (sheet) return;
  sheet = createSheet(template, { label: "Ingreso" });
  sheet.el.addEventListener("click", (e) => {
    const cur = e.target.closest("[data-currency]");
    if (cur) { currency = cur.dataset.currency; syncFields(); }
  });
  $("#if-frequency").addEventListener("change", syncFields);
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
    };
    $("#if-save").disabled = true;
    try {
      await api(editing ? `/api/incomes/${editing.id}` : "/api/incomes",
        { method: editing ? "PATCH" : "POST", body });
      toast(editing ? "Ingreso actualizado" : "Ingreso guardado");
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
  $("#if-delete").hidden = !income;
  $("#if-error").textContent = "";
  syncFields();
  sheet.open();
}
