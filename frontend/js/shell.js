// =========================================================================
// shell.js · El "esqueleto" común a todas las pantallas privadas:
// menú lateral (escritorio), barra inferior (celular), botón "+" de gasto
// rápido y menú "Más". Cada página solo escribe su <main>.
// =========================================================================

import { api, auth, isDemoEmail, requireLogin } from "./api.js";
import { openExpenseSheet } from "./expense-form.js";
import { isInstalled, maybeSuggestInstall, openInstall } from "./install.js";
import { setupRefresh } from "./refresh.js";
import { resumeTour, startTour } from "./tour.js";
import { confirmDialog, createSheet, esc, icons, reducedMotion, toast, toggleTheme } from "./ui.js";

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
    <div class="border-t mt-6 pt-5" style="border-color:var(--border)" id="acc-real">
      <details>
        <summary class="font-medium cursor-pointer">Cambiar contraseña</summary>
        <form id="acc-pass-form" class="space-y-3 mt-3" novalidate>
          <label class="field"><span>Contraseña actual</span><input id="acc-pass-old" type="password" class="input" autocomplete="current-password" /></label>
          <label class="field"><span>Contraseña nueva</span><input id="acc-pass-new" type="password" class="input" autocomplete="new-password" placeholder="Mínimo 8 caracteres" /></label>
          <p class="form-error" id="acc-pass-error"></p>
          <button class="btn btn-ghost w-full">Cambiar contraseña</button>
        </form>
      </details>
      <label class="flex items-start gap-3 mt-5 cursor-pointer">
        <input type="checkbox" id="acc-share" class="w-4 h-4 mt-1" style="accent-color:var(--primary)" />
        <span class="text-sm"><b>Compartir mis datos con el administrador</b>
          <span class="muted block text-xs mt-0.5">Para que pueda ver lo que cargaste y ayudarte si algo no te cierra. Lo podés desactivar cuando quieras.
            Aunque no lo actives, tu contraseña nunca la ve nadie.</span></span>
      </label>
    </div>
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
    q("#acc-pass-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const err = (m) => (q("#acc-pass-error").textContent = m);
      const current = q("#acc-pass-old").value;
      const next = q("#acc-pass-new").value;
      if (next.length < 8) return err("La nueva tiene que tener al menos 8 caracteres.");
      try {
        const { access_token } = await api("/api/users/me/password", { method: "POST", body: { current_password: current, new_password: next } });
        auth.renew(access_token);  // este aparato sigue adentro; los demás tienen que volver a entrar
        q("#acc-pass-form").reset();
        err("");
        toast("Contraseña cambiada. Se cerró la sesión en tus otros aparatos.");
      } catch (error) { err(error.message); }
    });
    q("#acc-share").addEventListener("change", async () => {
      const shares = q("#acc-share").checked;
      await api("/api/users/me", { method: "PATCH", body: { shares_data: shares } });
      mePromise = null;  // la próxima vez se piden los datos actualizados
      toast(shares ? "Ahora el administrador puede ver tus datos" : "Dejaste de compartir tus datos");
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
  q("#acc-share").checked = Boolean(me.shares_data);
  q("#acc-real").hidden = demo;  // la demo no tiene contraseña ni nada que compartir
  icons();
  accountSheet.open();
}

// --- Hoja "Enviar un comentario": algo que no se entendió, un error, una idea ---
let feedbackSheet;
function openFeedback() {
  feedbackSheet ??= createSheet(`
    <form id="fb-form" novalidate>
      <h3 class="font-display text-xl font-bold mb-1">Contanos qué pensás</h3>
      <p class="muted text-sm mb-4">¿Algo no se entendió, no funcionó o se te ocurre una idea? Todo sirve para mejorar la app.</p>
      <textarea id="fb-text" class="input min-h-32" maxlength="1000" placeholder="Ej: no entendí qué significa “plata libre”…" autofocus></textarea>
      <p class="form-error my-2" id="fb-error"></p>
      <button class="btn btn-primary w-full">Enviar</button>
    </form>`, { label: "Enviar un comentario" });
  const q = (s) => feedbackSheet.el.querySelector(s);
  if (!feedbackSheet.ready) {
    feedbackSheet.ready = true;
    q("#fb-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const message = q("#fb-text").value.trim();
      if (!message) return (q("#fb-error").textContent = "Escribí tu comentario.");
      try {
        await api("/api/users/me/feedback", { method: "POST", body: { message, page: location.pathname } });
        q("#fb-text").value = "";
        feedbackSheet.close();
        toast("¡Gracias! Lo recibimos");
      } catch (err) { q("#fb-error").textContent = err.message; }
    });
  }
  q("#fb-error").textContent = "";
  feedbackSheet.open();
}

/** Aviso arriba de todo cuando se está usando una cuenta demo. */
function showDemoBanner() {
  const banner = document.createElement("div");
  banner.id = "demo-banner";
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
 * Los bloques entran cuando llegás a ellos con el scroll, no todos al abrir la pantalla
 * (si no, los de abajo terminan su animación antes de que los veas).
 */
function revealOnScroll() {
  if (reducedMotion() || !("IntersectionObserver" in window)) return;
  const opened = performance.now();
  const seen = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      // La demora escalonada es para la primera vista; al scrollear, entra enseguida
      if (performance.now() - opened > 1000) entry.target.style.animationDelay = "0s";
      entry.target.classList.remove("rise-wait");
      seen.unobserve(entry.target);
    });
  }, { rootMargin: "0px 0px -5% 0px" });
  document.querySelectorAll("main .rise").forEach((el) => {
    el.classList.add("rise-wait");
    seen.observe(el);
  });
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
  // overflow-y-auto: con zoom alto la ventana "mide" menos y el menú tiene que poder scrollear
  sidebar.className = "hidden md:flex flex-col w-60 shrink-0 pt-8 sticky top-0 h-screen overflow-y-auto";
  sidebar.innerHTML = `
      <a href="/dashboard.html" class="font-display text-2xl font-bold mb-8 px-3">Vault<span class="text-primary">Base</span></a>
      <nav class="flex flex-col gap-1">
        ${NAV.map((n) => `<a class="sidebar-link" href="${n.href}" ${current(n.href)}>
          <i data-lucide="${n.icon}"></i>${n.label}</a>`).join("")}
      </nav>
      <div class="mt-auto mb-6 space-y-1">
        <button class="sidebar-link w-full" data-action="account"><i data-lucide="user-round"></i>Mi cuenta</button>
        ${isInstalled() ? "" : `<button class="sidebar-link w-full" data-action="install"><i data-lucide="monitor-smartphone"></i>Instalar la app</button>`}
        <button class="sidebar-link w-full" data-action="tour"><i data-lucide="graduation-cap"></i>Ver el tutorial</button>
        <button class="sidebar-link w-full" data-action="feedback"><i data-lucide="message-circle"></i>Enviar un comentario</button>
        <a class="sidebar-link" href="/admin.html" data-admin-link hidden><i data-lucide="shield"></i>Administrador</a>
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
      ${isInstalled() ? "" : `<button class="sidebar-link w-full" data-action="install"><i data-lucide="smartphone"></i>Instalar en el celular</button>`}
      <button class="sidebar-link w-full" data-action="tour"><i data-lucide="graduation-cap"></i>Ver el tutorial</button>
      <button class="sidebar-link w-full" data-action="feedback"><i data-lucide="message-circle"></i>Enviar un comentario</button>
      <a class="sidebar-link" href="/admin.html" data-admin-link hidden><i data-lucide="shield"></i>Administrador</a>
      <button class="sidebar-link w-full" data-action="theme"><i data-lucide="sun-moon"></i>Claro / oscuro</button>
      <button class="sidebar-link w-full" data-action="logout"><i data-lucide="log-out"></i>Salir</button>
    </div>`, { label: "Más opciones" });

  document.addEventListener("click", (e) => {
    const action = e.target.closest("[data-action]")?.dataset.action;
    if (action === "theme") toggleTheme();
    if (action === "logout") logout();
    if (action === "more") { e.preventDefault(); more.open(); }
    if (action === "account") { more.close(); openAccount(); }
    if (action === "install") { more.close(); openInstall(); }
    if (action === "feedback") { more.close(); openFeedback(); }
    if (action === "tour") {
      // El tutorial recorre el Inicio: si estás en otra pantalla, vamos ahí
      more.close();
      if (location.pathname === "/dashboard.html") startTour();
      else location.href = "/dashboard.html?tutorial=1";
    }
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
    document.querySelectorAll("[data-admin-link]").forEach((el) => (el.hidden = !me.is_admin));
  }).catch(() => {});

  // El teclado del iPhone puede correr la página y dejarla corrida al cerrarse: la devolvemos a su lugar
  document.addEventListener("focusout", () => setTimeout(() => {
    const typing = document.activeElement?.matches("input, textarea, select");
    if (scrollY && !typing && matchMedia("(max-width: 767px)").matches) scrollTo(0, 0);
  }, 100));

  revealOnScroll();
  maybeSuggestInstall();
  setupRefresh();
  resumeTour();  // si venías en medio del recorrido completo, sigue en esta pantalla
  icons();
  return true;
}

export { esc };
