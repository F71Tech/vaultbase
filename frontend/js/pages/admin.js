// admin.js · Panel del administrador: uso de la app, links para nueva
// contraseña, comentarios y (solo con permiso) los datos de cada persona.

import { api } from "../api.js";
import { money, shortDate } from "../format.js";
import { FREQUENCY, KIND } from "../labels.js";
import { mountShell } from "../shell.js";
import { esc, icons, toast } from "../ui.js";

const $ = (id) => document.getElementById(id);
let users = [];

// La base guarda las horas en UTC (a veces sin la "Z" que lo indica)
const utc = (iso) => new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
const localDay = (iso) => utc(iso).toLocaleDateString("es-UY", { day: "numeric", month: "short" });

/** "hace 2 h", "hace 3 d", "nunca" */
function ago(iso) {
  if (!iso) return "nunca";
  const minutes = (Date.now() - utc(iso)) / 60000;
  if (minutes < 60) return `hace ${Math.max(1, Math.round(minutes))} min`;
  if (minutes < 60 * 24) return `hace ${Math.round(minutes / 60)} h`;
  return `hace ${Math.round(minutes / 60 / 24)} d`;
}

function userRow(u) {
  const stats = [
    [u.expenses, "gastos"], [u.incomes, "ingresos"], [u.goals, "metas"],
    [u.subscriptions, "suscripciones"], [u.commissions, "comisiones"], [u.feedback, "comentarios"],
  ].map(([n, label]) => `<span class="chip" style="padding:2px 8px;font-size:.7rem">${n} ${label}</span>`).join("");
  return `
    <div class="rounded-xl p-3" style="background:var(--surface-2)">
      <div class="flex flex-wrap items-center gap-2 justify-between">
        <div class="min-w-0">
          <div class="font-medium truncate">${esc(u.name)} <span class="muted text-xs">${esc(u.email)}</span></div>
          <div class="muted text-xs">Se anotó el ${localDay(u.created_at)} · última actividad: ${ago(u.last_activity)}</div>
        </div>
        <div class="flex gap-2">
          <button class="btn btn-ghost text-xs py-1.5" data-reset="${u.id}"><i data-lucide="key-round" class="w-3.5 h-3.5"></i>Link nueva contraseña</button>
          ${u.shares_data ? `<button class="btn btn-primary text-xs py-1.5" data-view="${u.id}"><i data-lucide="eye" class="w-3.5 h-3.5"></i>Ver datos</button>`
                          : `<span class="muted text-xs self-center" title="La persona no activó 'Compartir mis datos'">🔒 datos privados</span>`}
        </div>
      </div>
      <div class="flex flex-wrap gap-1.5 mt-2">${stats}</div>
    </div>`;
}

function renderUserData(d) {
  const m = d.money;
  const list = (rows) => rows.length ? `<ul class="text-sm space-y-1">${rows.join("")}</ul>` : `<p class="muted text-sm">Nada cargado.</p>`;
  const li = (left, right) => `<li class="flex justify-between gap-3"><span class="truncate">${left}</span><span class="tabular-nums">${right}</span></li>`;
  $("user-data-title").textContent = `Datos de ${d.user.name}`;
  $("user-data").innerHTML = `
    ${m ? `<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5 text-sm">
      <div><div class="muted text-xs">Plata hoy</div><b>${money(m.current_cents)}</b></div>
      <div><div class="muted text-xs">Podés ahorrar</div><b>${money(m.can_save_cents)}</b></div>
      <div><div class="muted text-xs">Gasto por día</div><b>${money(m.daily_spending_cents)}</b></div>
      <div><div class="muted text-xs">Próximo cobro</div><b>${shortDate(m.next_pay)}</b></div></div>` : ""}
    <div class="grid md:grid-cols-2 gap-5">
      <div><h3 class="font-medium mb-2">Ingresos</h3>${list(d.incomes.map((i) => li(`${esc(i.source)} <span class="muted text-xs">${FREQUENCY[i.frequency] ?? i.frequency}${i.food_only ? " · ticket" : ""}</span>`, money(i.amount_cents))))}</div>
      <div><h3 class="font-medium mb-2">Metas</h3>${list(d.goals.map((g) => li(esc(g.name), `${money(g.saved_cents)} / ${money(g.target_cents)}`)))}</div>
      <div class="md:col-span-2"><h3 class="font-medium mb-2">Últimos gastos</h3>${list(d.expenses.map((e) =>
        li(`${shortDate(e.date)} · ${esc(e.description || e.subcategory || e.category)} <span class="muted text-xs">${KIND[e.kind] ?? e.kind}</span>`, money(e.amount_cents))))}</div>
    </div>`;
  $("user-data-card").hidden = false;
  $("user-data-card").scrollIntoView({ behavior: "smooth" });
}

async function load() {
  let feedback;
  try {
    [users, feedback] = await Promise.all([api("/api/admin/users"), api("/api/admin/feedback")]);
  } catch {
    document.querySelector("main").innerHTML = `<div class="card p-8 text-center"><h1 class="font-display text-2xl font-bold">Solo para el administrador</h1>
      <p class="muted mt-2">Tu cuenta no tiene acceso a esta página.</p><a href="/dashboard.html" class="btn btn-primary mt-5">Volver al inicio</a></div>`;
    return;
  }
  $("user-count").textContent = `${users.length} ${users.length === 1 ? "persona" : "personas"}`;
  $("users").innerHTML = users.length ? users.map(userRow).join("") : `<p class="muted text-sm">Todavía no se anotó nadie (las demos no cuentan).</p>`;
  $("feedback").innerHTML = feedback.length ? feedback.map((f) => `
    <div class="rounded-xl p-3" style="background:var(--surface-2)">
      <p class="text-sm">${esc(f.message)}</p>
      <p class="muted text-xs mt-1">${esc(f.name)} · ${esc(f.page || "")} · ${ago(f.created_at)}</p>
    </div>`).join("") : `<p class="muted text-sm">Sin comentarios todavía.</p>`;
  icons();
}

document.addEventListener("click", async (e) => {
  const reset = e.target.closest("[data-reset]");
  const view = e.target.closest("[data-view]");
  if (reset) {
    const { url } = await api(`/api/admin/users/${reset.dataset.reset}/reset-link`, { method: "POST" });
    try { await navigator.clipboard.writeText(url); toast("Link copiado: mandáselo por WhatsApp (vence en 24 h)"); }
    catch { prompt("Copiá este link y mandáselo (vence en 24 h):", url); }
  }
  if (view) renderUserData(await api(`/api/admin/users/${view.dataset.view}/data`));
});
$("user-data-close").addEventListener("click", () => ($("user-data-card").hidden = true));

if (mountShell()) load();
