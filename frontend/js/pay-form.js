// pay-form.js · Hoja para anotar un cobro REAL ("¿cuánto te entró?").
//
// El sueldo mensual es una estimación. Cuando cobrás, anotás lo que de verdad
// te entró: ese número manda para ese mes y el próximo cobro se estima con él.
// Si ese mes ya tenía un cobro anotado, se corrige (no se duplica).

import { api } from "./api.js";
import { centsToInput, money, parseMoney, shortDate, toISO } from "./format.js";
import { confirmDialog, createSheet, notifyDataChanged, toast } from "./ui.js";

let sheet;
let income = null;
let records = [];   // cobros reales ya anotados de este ingreso
let kind = "pay";

const template = `
  <form id="pay-form" novalidate>
    <h3 class="font-display text-xl font-bold mb-1">¿Cuánto te entró?</h3>
    <p class="muted text-sm mb-4" id="pf-sub"></p>
    <div class="segmented flex w-full mb-3" role="group" aria-label="Qué cobraste" id="pf-kind-wrap">
      <button type="button" class="flex-1 text-center" data-pay-kind="pay">Cobro del mes</button>
      <button type="button" class="flex-1 text-center" data-pay-kind="advance">Adelanto</button>
    </div>
    <input id="pf-amount" class="amount-input my-3" inputmode="decimal" placeholder="0" aria-label="Monto en mano" autofocus />
    <label class="field mb-2"><span>Fecha en que te entró</span><input id="pf-date" type="date" class="input" /></label>
    <p class="muted text-xs mb-3">Lo que te entró en mano (lo que dice "Líquido" en el recibo). Reemplaza la estimación de ese mes,
      y el próximo cobro se estima con este número hasta que anotes el nuevo.</p>
    <p class="form-error mb-2" id="pf-error"></p>
    <div class="flex gap-3">
      <button type="button" class="btn btn-danger" id="pf-delete" hidden><i data-lucide="trash-2" class="w-4 h-4"></i></button>
      <button type="submit" class="btn btn-primary flex-1">Guardar</button>
    </div>
  </form>`;

const $ = (sel) => sheet.el.querySelector(sel);

/** El último día de cobro (o de adelanto) de un ingreso mensual: hoy o antes. */
export function lastPayDay(inc, which = "pay") {
  const day = which === "advance" ? (inc.advance_day ?? 15) : (inc.pay_day ?? 1);
  const today = new Date();
  const onDay = (y, m) => new Date(y, m, Math.min(day, new Date(y, m + 1, 0).getDate()));
  let date = onDay(today.getFullYear(), today.getMonth());
  if (date > today) date = onDay(today.getFullYear(), today.getMonth() - 1);
  return toISO(date);
}

const sameMonth = (a, b) => a.slice(0, 7) === b.slice(0, 7);
const existing = () => records.find((r) => r.kind === kind && sameMonth(r.date, $("#pf-date").value));

function render() {
  sheet.el.querySelectorAll("[data-pay-kind]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.payKind === kind));
  const rec = existing();
  $("#pf-delete").hidden = !rec;
  $("#pf-sub").textContent = rec
    ? `Ya anotaste ${money(rec.amount_cents)} el ${shortDate(rec.date)}: lo corregís.`
    : `${income.source} · lo que te entró de verdad ese día.`;
}

function ensureSheet() {
  if (sheet) return;
  sheet = createSheet(template, { label: "Cobro real" });
  sheet.el.addEventListener("click", (e) => {
    const k = e.target.closest("[data-pay-kind]");
    if (!k) return;
    kind = k.dataset.payKind;
    $("#pf-date").value = lastPayDay(income, kind);
    const rec = existing();
    $("#pf-amount").value = rec ? centsToInput(rec.amount_cents) : "";
    render();
  });
  $("#pf-date").addEventListener("change", render);
  $("#pf-delete").addEventListener("click", async () => {
    const rec = existing();
    if (!rec || !(await confirmDialog("¿Borrar este cobro real? Se vuelve a usar la estimación."))) return;
    await api(`/api/pay-records/${rec.id}`, { method: "DELETE" });
    toast("Cobro borrado");
    sheet.close();
    notifyDataChanged();
  });
  $("#pay-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const amount = parseMoney($("#pf-amount").value);
    if (amount === null) return ($("#pf-error").textContent = "Escribí cuánto te entró.");
    const date = $("#pf-date").value;
    if (!date) return ($("#pf-error").textContent = "Elegí la fecha.");
    const rec = existing();
    try {
      await api(rec ? `/api/pay-records/${rec.id}` : "/api/pay-records", {
        method: rec ? "PATCH" : "POST",
        body: rec ? { date, amount_cents: amount } : { income_id: income.id, date, kind, amount_cents: amount },
      });
      toast(`Cobro anotado: ${money(amount)}`);
      sheet.close();
      notifyDataChanged();
    } catch (err) {
      $("#pf-error").textContent = err.message;
    }
  });
}

/** Abre la hoja para anotar un cobro real de un ingreso mensual. */
export async function openPaySheet(inc, { which = "pay" } = {}) {
  ensureSheet();
  income = inc;
  kind = which;
  records = (await api("/api/pay-records")).filter((r) => r.income_id === inc.id);
  $("#pf-kind-wrap").hidden = !inc.advance_cents;
  $("#pf-date").value = lastPayDay(inc, kind);
  const rec = existing();
  $("#pf-amount").value = rec ? centsToInput(rec.amount_cents) : "";
  $("#pf-error").textContent = "";
  render();
  sheet.open();
}
