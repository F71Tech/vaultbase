// =========================================================================
// shell.js · El "esqueleto" común a todas las pantallas privadas:
// menú lateral (escritorio), barra inferior (celular), botón "+" de gasto
// rápido y menú "Más". Cada página solo escribe su <main>.
// =========================================================================

import { api, auth, requireLogin } from "./api.js";
import { openExpenseSheet } from "./expense-form.js";
import { createSheet, esc, icons, toggleTheme } from "./ui.js";

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
      <button class="sidebar-link w-full" data-action="theme"><i data-lucide="sun-moon"></i>Claro / oscuro</button>
      <button class="sidebar-link w-full" data-action="logout"><i data-lucide="log-out"></i>Salir</button>
    </div>`, { label: "Más opciones" });

  document.addEventListener("click", (e) => {
    const action = e.target.closest("[data-action]")?.dataset.action;
    if (action === "theme") toggleTheme();
    if (action === "logout") logout();
    if (action === "more") { e.preventDefault(); more.open(); }
  });

  getMe().then((me) => {
    document.querySelectorAll("[data-me-name]").forEach((el) => (el.textContent = me.name));
    document.querySelectorAll("[data-me-email]").forEach((el) => (el.textContent = me.email));
  }).catch(() => {});

  icons();
  return true;
}

export { esc };
