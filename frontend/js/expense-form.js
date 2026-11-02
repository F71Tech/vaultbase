// =========================================================================
// expense-form.js · La hoja para cargar o editar un gasto.
//
// La misma pieza sirve para dos cosas:
//   - Gasto rápido (botón "+"): monto, categoría y listo. La fecha es hoy.
//   - Editar un gasto existente: con todos los campos y el botón Borrar.
// =========================================================================

import { api } from "./api.js";
import { centsToInput, parseMoney, todayISO } from "./format.js";
import { getCategories, KIND } from "./labels.js";
import { confirmDialog, createSheet, esc, icons, notifyDataChanged, toast } from "./ui.js";

let sheet;          // la hoja se crea una sola vez y se reutiliza
let editing = null; // gasto que se está editando (null = gasto nuevo)
let openedKind = "variable"; // con qué tipo se abrió la hoja ("+" = variable)
const state = { category: "food", subcategory: null, currency: "UYU", kind: "variable" };

function template(cats) {
  const catButtons = cats.list.map((c) => `
    <button type="button" class="cat-btn" data-cat="${c.key}" aria-pressed="false">
      <i data-lucide="${c.icon}"></i>${esc(c.label)}
    </button>`).join("");

  return `
  <form id="expense-form" novalidate>
    <div class="flex items-center justify-between mb-1">
      <h3 class="font-display text-xl font-bold" id="ef-title">Gasto rápido</h3>
      <div class="segmented" role="group" aria-label="Moneda">
        <button type="button" data-currency="UYU" aria-pressed="true">$U</button>
        <button type="button" data-currency="USD" aria-pressed="false">US$</button>
      </div>
    </div>
    <p class="muted text-sm mb-2" id="ef-subtitle">Hoy · tocá el monto para escribir</p>

    <input id="ef-amount" class="amount-input my-3" inputmode="decimal" autocomplete="off"
           placeholder="0" aria-label="Monto" autofocus />

    <div class="grid grid-cols-4 sm:grid-cols-5 gap-2 mb-3">${catButtons}</div>
    <div id="ef-subs" class="flex flex-wrap gap-2 mb-4"></div>
    <p id="ef-fixed-hint" class="text-xs rounded-xl bg-primary-soft p-2.5 mb-4 flex gap-2 items-center" hidden>
      <i data-lucide="repeat" class="w-4 h-4 text-primary shrink-0"></i>
      <span>Esto suele repetirse todos los meses: lo marcamos como <b>gasto fijo</b>. Si no, cambialo en "Tipo".</span></p>

    <label class="field mb-3"><span>Descripción (opcional)</span>
      <input id="ef-description" class="input" maxlength="120" placeholder="Ej: alfajor, taxi al centro…" />
    </label>

    <button type="button" id="ef-more" class="text-sm text-primary font-medium mb-3 inline-flex items-center gap-1">
      <i data-lucide="sliders-horizontal" class="w-4 h-4"></i><span>Más opciones</span>
    </button>
    <div id="ef-advanced" class="grid grid-cols-2 gap-3 mb-4" hidden>
      <label class="field"><span>Fecha</span><input id="ef-date" type="date" class="input" /></label>
      <label class="field"><span>Tipo</span>
        <select id="ef-kind" class="input">
          ${Object.entries(KIND).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}
        </select>
      </label>
      <label class="field col-span-2" id="ef-end-wrap" hidden><span>Se repite hasta (vacío = sin fin)</span>
        <input id="ef-end" type="date" class="input" />
      </label>
    </div>

    <p class="form-error mb-2" id="ef-error"></p>
    <div class="flex gap-3">
      <button type="button" class="btn btn-danger" id="ef-delete" hidden><i data-lucide="trash-2" class="w-4 h-4"></i></button>
      <button type="submit" class="btn btn-primary flex-1" id="ef-save">Guardar</button>
    </div>
  </form>`;
}

const $ = (sel) => sheet.el.querySelector(sel);

function renderSelection(cats) {
  sheet.el.querySelectorAll("[data-cat]").forEach((b) =>
    b.setAttribute("aria-pressed", b.dataset.cat === state.category));
  sheet.el.querySelectorAll("[data-currency]").forEach((b) =>
    b.setAttribute("aria-pressed", b.dataset.currency === state.currency));
  const subs = cats.byKey[state.category]?.subcategories ?? [];
  $("#ef-subs").innerHTML = subs.map((s) => `
    <button type="button" class="chip" data-sub="${s.key}" aria-pressed="${s.key === state.subcategory}">
      ${esc(s.label)}</button>`).join("");
  $("#ef-end-wrap").hidden = $("#ef-kind").value !== "fixed";
}

// Gastos que casi siempre se repiten igual cada mes. Si alguien los carga con
// el "+" (que por defecto anota un gasto del día), los pasamos a "fijo": así
// cuentan todos los meses y el plan de metas no sugiere recortarlos.
const USUALLY_FIXED = new Set([
  "rent", "common_fees", "electricity", "water", "internet_phone", "gas", "health_plan", "tuition",
]);

function suggestFixed() {
  const fixed = !editing && USUALLY_FIXED.has(state.subcategory);
  if (!editing) {
    $("#ef-kind").value = fixed ? "fixed" : openedKind;  // vuelve al tipo con el que se abrió
    if (fixed) $("#ef-advanced").hidden = false;  // para que vea el tipo y pueda cambiarlo
  }
  $("#ef-fixed-hint").hidden = !fixed;
}

async function ensureSheet() {
  if (sheet) return;
  const cats = await getCategories();
  sheet = createSheet(template(cats), { label: "Cargar gasto" });

  // Elegir categoría (y limpiar la subcategoría, que ya no correspondería)
  sheet.el.addEventListener("click", (e) => {
    const cat = e.target.closest("[data-cat]");
    const sub = e.target.closest("[data-sub]");
    const cur = e.target.closest("[data-currency]");
    if (cat) { state.category = cat.dataset.cat; state.subcategory = null; }
    if (sub) {
      state.subcategory = state.subcategory === sub.dataset.sub ? null : sub.dataset.sub;
      suggestFixed();
    }
    if (cur) { state.currency = cur.dataset.currency; }
    if (cat || sub || cur) renderSelection(cats);
  });
  $("#ef-kind").addEventListener("change", () => renderSelection(cats));
  $("#ef-more").addEventListener("click", () => { $("#ef-advanced").hidden = !$("#ef-advanced").hidden; });
  $("#ef-delete").addEventListener("click", onDelete);
  $("#expense-form").addEventListener("submit", (e) => { e.preventDefault(); onSave(); });
  sheet.render = () => renderSelection(cats);
}

async function onSave() {
  const amount = parseMoney($("#ef-amount").value);
  if (!amount) {
    $("#ef-error").textContent = "Escribí un monto válido (ej: 60 o 1.500,50).";
    $("#ef-amount").focus();
    return;
  }
  const kind = $("#ef-kind").value;
  const body = {
    category: state.category,
    subcategory: state.subcategory,
    amount_cents: amount,
    currency: state.currency,
    kind,
    date: $("#ef-date").value || todayISO(),
    end_date: kind === "fixed" ? ($("#ef-end").value || null) : null,
    description: $("#ef-description").value.trim() || null,
  };
  const btn = $("#ef-save");
  btn.disabled = true;
  try {
    if (editing) {
      // Si cambió la moneda o la fecha, que el servidor recalcule la cotización
      if (body.currency !== editing.currency || body.date !== editing.date) body.exchange_rate = null;
      await api(`/api/expenses/${editing.id}`, { method: "PATCH", body });
      toast("Gasto actualizado");
    } else {
      await api("/api/expenses", { method: "POST", body });
      toast("Gasto guardado");
    }
    sheet.close();
    notifyDataChanged();
  } catch (err) {
    $("#ef-error").textContent = err.message;
  } finally {
    btn.disabled = false;
  }
}

async function onDelete() {
  if (!editing || !(await confirmDialog("¿Borrar este gasto?"))) return;
  try {
    await api(`/api/expenses/${editing.id}`, { method: "DELETE" });
    toast("Gasto borrado");
    sheet.close();
    notifyDataChanged();
  } catch (err) {
    toast(err.message, "error");
  }
}

/** Abre la hoja. Sin argumento = gasto nuevo; con un gasto = editarlo. */
export async function openExpenseSheet(expense = null, { kind = "variable" } = {}) {
  await ensureSheet();
  editing = expense;
  openedKind = kind;
  const e = expense ?? {};
  state.category = e.category ?? "food";
  state.subcategory = e.subcategory ?? null;
  state.currency = e.currency ?? "UYU";

  $("#ef-title").textContent = expense ? "Editar gasto" : kind === "fixed" ? "Nuevo gasto fijo" : "Gasto rápido";
  $("#ef-subtitle").textContent = expense ? "Cambiá lo que necesites" : "Hoy · tocá el monto para escribir";
  $("#ef-amount").value = expense ? centsToInput(e.amount_cents) : "";
  $("#ef-description").value = e.description ?? "";
  $("#ef-date").value = e.date ?? todayISO();
  $("#ef-kind").value = e.kind ?? kind;
  $("#ef-end").value = e.end_date ?? "";
  $("#ef-advanced").hidden = !(expense || kind === "fixed");
  $("#ef-delete").hidden = !expense;
  $("#ef-fixed-hint").hidden = true;
  $("#ef-error").textContent = "";
  sheet.render();
  icons();
  sheet.open();
}
