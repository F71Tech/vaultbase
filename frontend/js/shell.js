// =========================================================================
// shell.js · El "esqueleto" común a todas las pantallas privadas:
// menú lateral (escritorio), barra inferior (celular), botón "+" de gasto
// rápido y menú "Más". Cada página solo escribe su <main>.
// =========================================================================

import { api, auth, isDemoEmail, requireLogin } from "./api.js";
import { openExpenseSheet } from "./expense-form.js";
import { confirmDialog, createSheet, esc, icons, toast, toggleTheme } from "./ui.js";

const NAV = [
  { href: "/dashboard.html", icon: "layout-dashboard", label: "Inicio", short: "Inicio" },
  { href: "/movimientos.html", icon: "arrow-left-right", label: "Movimientos", short: "Movim." },
  { href: "/metas.html", icon: "target", label: "Metas", short: "Metas" },
  { href: "/simulador.html", icon: "calculator", label: "Simulador", short: "Simular" },
  { href: "/suscripciones.html", icon: "repeat", label: "Suscripciones", short: null },
  { href: "/sueldo.html", icon: "wallet", label: "Sueldo y aguinaldo", short: null },
];

let mePromise;
/** Datos del usuario logueado (se piden una sola vez por página). */
export const getMe = () => (mePromise ??= api("/api/users/me"));

function logout() {
  auth.clear();
  location.href = "/login.html";
}

// --- Hoja "Mi cuenta": cambiar el nombre o borrar la cuenta ---
let accountSheet;
async function openAccount() {
  const me = await getMe();
  const demo = isDemoEmail(me.email);
  accountSheet ??= createSheet(`
    <h3 class="font-display text-xl font-bold mb-1">Mi cuenta</h3>
    <p class="muted text-sm mb-4" id="acc-email"></p>
    <form id="acc-form" class="space-y-3" novalidate>
      <label class="field"><span>Nombre</span><input id="acc-name" class="input" maxlength="80" /></label>
      <button class="btn btn-primary w-full">Guardar</button>
    </form>
    <div class="border-t mt-6 pt-5" style="border-color:var(--border)">
      <div class="font-medium mb-1">Borrar mi cuenta</div>
      <p class="muted text-sm mb-3">Se borran tu cuenta y todos tus datos (gastos, metas, suscripciones…). No se puede deshacer.</p>
      <button class="btn btn-danger w-full" id="acc-delete"><i data-lucide="trash-2" class="w-4 h-4"></i>Borrar mi cuenta</button>
    </div>`, { label: "Mi cuenta" });
  const q = (s) => accountSheet.el.querySelector(s);
  if (!accountSheet.ready) {
    accountSheet.ready = true;
    q("#acc-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = q("#acc-name").value.trim();
      if (!name) return;
      await api("/api/users/me", { method: "PATCH", body: { name } });
      document.querySelectorAll("[data-me-name]").forEach((el) => (el.textContent = name));
      toast("Nombre actualizado");
      accountSheet.close();
    });
    q("#acc-delete").addEventListener("click", async () => {
      accountSheet.close();
      if (!(await confirmDialog("¿Seguro? Se borra tu cuenta con todos tus datos.", { confirmText: "Sí, borrar todo" }))) return;
      await api("/api/users/me", { method: "DELETE" });
      auth.clear();
      location.href = "/";
    });
  }
  q("#acc-email").textContent = demo ? "Cuenta demo (se borra sola en unas horas)" : me.email;
  q("#acc-name").value = me.name;
  icons();
  accountSheet.open();
}

/** Aviso arriba de todo cuando se está usando una cuenta demo. */
function showDemoBanner() {
  const banner = document.createElement("div");
  banner.className = "card px-4 py-3 flex flex-wrap items-center gap-3 text-sm fade";
  banner.style.borderColor = "var(--accent)";
  banner.innerHTML = `
    <i data-lucide="flask-conical" class="w-4 h-4 text-accent shrink-0"></i>
    <span class="flex-1 min-w-[12rem]"><b>Estás en la demo.</b> <span class="muted">Datos de ejemplo: tocá, cargá y probá todo. Se borra sola en unas horas.</span></span>
    <a href="#" class="btn btn-primary text-sm py-1.5" data-action="signup">Crear mi cuenta</a>`;
  document.querySelector("main").prepend(banner);
  icons();
}

/**
 * Completa el esqueleto de la página: el HTML ya trae
 *   <div class="app-layout"><aside id="sidebar"></aside><main>…</main></div>
 * y acá rellenamos el menú. (No movemos el <main> de lugar: mover un elemento
 * reinicia sus animaciones y las tarjetas "parpadeaban".)
 * Devuelve false si no hay sesión (y redirige al login).
 */
export function mountShell() {
  if (!requireLogin()) return false;
  const path = location.pathname;
  const current = (href) => (href === path ? 'aria-current="page"' : "");

  // --- Menú lateral (escritorio) ---
  const sidebar = document.getElementById("sidebar");
  sidebar.className = "hidden md:flex flex-col w-60 shrink-0 pt-8 sticky top-0 h-screen";
  sidebar.innerHTML = `
      <a href="/dashboard.html" class="font-display text-2xl font-bold mb-8 px-3">Vault<span class="text-primary">Base</span></a>
      <nav class="flex flex-col gap-1">
        ${NAV.map((n) => `<a class="sidebar-link" href="${n.href}" ${current(n.href)}>
          <i data-lucide="${n.icon}"></i>${n.label}</a>`).join("")}
      </nav>
      <div class="mt-auto mb-6 space-y-1">
        <button class="sidebar-link w-full" data-action="account"><i data-lucide="user-round"></i>Mi cuenta</button>
        <button class="sidebar-link w-full" data-action="theme"><i data-lucide="sun-moon"></i>Claro / oscuro</button>
        <button class="sidebar-link w-full" data-action="logout"><i data-lucide="log-out"></i>Salir</button>
        <div class="px-3 pt-3 text-sm"><div class="font-medium" data-me-name>&nbsp;</div>
          <div class="muted truncate text-xs" data-me-email></div></div>
      </div>`;

  // --- Barra inferior (celular) ---
  const bottom = document.createElement("nav");
  bottom.className = "bottom-nav md:hidden";
  bottom.setAttribute("aria-label", "Navegación principal");
  bottom.innerHTML = `<div class="grid grid-cols-5">
    ${NAV.filter((n) => n.short).map((n) => `<a href="${n.href}" ${current(n.href)}>
      <i data-lucide="${n.icon}"></i>${n.short}</a>`).join("")}
    <a href="#" data-action="more"><i data-lucide="menu"></i>Más</a></div>`;

  // --- Botón flotante de gasto rápido ---
  const fab = document.createElement("button");
  fab.className = "fab";
  fab.setAttribute("aria-label", "Cargar gasto rápido");
  fab.innerHTML = `<i data-lucide="plus"></i>`;
  fab.addEventListener("click", () => openExpenseSheet());

  document.body.append(bottom, fab);

  // --- Menú "Más" (celular) ---
  const more = createSheet(`
    <h3 class="font-display text-xl font-bold mb-4">Más</h3>
    <div class="grid gap-1">
      ${NAV.filter((n) => !n.short).map((n) => `<a class="sidebar-link" href="${n.href}" ${current(n.href)}>
        <i data-lucide="${n.icon}"></i>${n.label}</a>`).join("")}
      <button class="sidebar-link w-full" data-action="account"><i data-lucide="user-round"></i>Mi cuenta</button>
      <button class="sidebar-link w-full" data-action="theme"><i data-lucide="sun-moon"></i>Claro / oscuro</button>
      <button class="sidebar-link w-full" data-action="logout"><i data-lucide="log-out"></i>Salir</button>
    </div>`, { label: "Más opciones" });

  document.addEventListener("click", (e) => {
    const action = e.target.closest("[data-action]")?.dataset.action;
    if (action === "theme") toggleTheme();
    if (action === "logout") logout();
    if (action === "more") { e.preventDefault(); more.open(); }
    if (action === "account") { more.close(); openAccount(); }
    if (action === "signup") {
      // De la demo a una cuenta real: salimos de la demo y vamos al registro
      e.preventDefault();
      auth.clear();
      location.href = "/login.html?mode=register";
    }
  });

  getMe().then((me) => {
    if (isDemoEmail(me.email)) showDemoBanner();
    document.querySelectorAll("[data-me-name]").forEach((el) => (el.textContent = me.name));
    document.querySelectorAll("[data-me-email]").forEach((el) => (el.textContent = isDemoEmail(me.email) ? "Cuenta demo" : me.email));
  }).catch(() => {});

  icons();
  return true;
}

export { esc };
