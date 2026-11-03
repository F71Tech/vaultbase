// =========================================================================
// install.js · "Agregá VaultBase a tu pantalla de inicio".
//
// - Android / Chrome / Edge: el navegador avisa que la app se puede instalar
//   (evento "beforeinstallprompt") y mostramos un botón "Instalar".
// - iPhone / iPad: Safari NO tiene ese botón automático; hay que hacerlo a mano
//   (Compartir → "Agregar a inicio"). Mostramos las instrucciones con dibujos.
// El aviso sale solo una vez cada 10 días si lo cerrás, y nunca si ya la abriste
// instalada.
// =========================================================================

import { createSheet, icons } from "./ui.js";

const KEY = "vb-install-dismissed";
const SNOOZE_DAYS = 10;
let deferredPrompt = null;  // el "permiso para instalar" que da Chrome/Android

export const isInstalled = () =>
  matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;

const isIOS = () =>
  /iphone|ipad|ipod/i.test(navigator.userAgent)
  || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);  // iPad "disfrazado" de Mac

function snoozed() {
  try { return Date.now() - Number(localStorage.getItem(KEY) || 0) < SNOOZE_DAYS * 86400000; } catch { return false; }
}
function snooze() {
  try { localStorage.setItem(KEY, String(Date.now())); } catch { /* sin almacenamiento */ }
}

const step = (n, html) => `
  <li class="flex gap-3 items-start">
    <span class="grid place-items-center w-7 h-7 rounded-full bg-primary-soft text-primary text-sm font-bold shrink-0">${n}</span>
    <span class="pt-0.5">${html}</span>
  </li>`;

function sheetHTML() {
  const ios = isIOS();
  const steps = ios ? [
    step(1, `Tocá <b>Compartir</b> <i data-lucide="share" class="inline w-4 h-4 text-primary"></i> (abajo en Safari, o arriba a la derecha en iPad).`),
    step(2, `Bajá y elegí <b>"Agregar a inicio"</b> <i data-lucide="square-plus" class="inline w-4 h-4 text-primary"></i>.`),
    step(3, `Tocá <b>"Agregar"</b>. ¡Listo! VaultBase queda con su ícono, como cualquier app.`),
  ] : [];
  return `
    <div class="flex gap-4 items-center mb-4">
      <img src="/icons/apple-touch-icon.png" alt="" class="w-14 h-14 rounded-2xl shrink-0" />
      <div>
        <h3 class="font-display text-xl font-bold">Tené VaultBase en tu celular</h3>
        <p class="muted text-sm">Se abre desde la pantalla de inicio, a pantalla completa, sin la barra del navegador.</p>
      </div>
    </div>
    ${ios ? `<ol class="space-y-3 text-sm mb-5">${steps.join("")}</ol>
      <p class="muted text-xs mb-4">Tiene que ser desde <b>Safari</b> (en otros navegadores de iPhone, buscá la misma opción en su menú).</p>`
      : deferredPrompt ? `<button class="btn btn-primary w-full mb-3" data-install-now><i data-lucide="download" class="w-4 h-4"></i>Instalar la app</button>`
      : `<p class="text-sm mb-4">Abrí el menú del navegador (<b>⋮</b>) y elegí <b>"Instalar app"</b> o <b>"Agregar a la pantalla de inicio"</b>.</p>`}
    <button class="btn btn-ghost w-full" data-close data-install-later>Ahora no</button>`;
}

let sheet;
/** Abre las instrucciones (también desde el menú, cuando el usuario quiera). */
export function openInstall() {
  sheet?.el.remove();
  sheet = createSheet(sheetHTML(), { label: "Instalar la app" });
  sheet.el.addEventListener("click", async (e) => {
    if (e.target.closest("[data-install-later]")) snooze();
    if (e.target.closest("[data-install-now]") && deferredPrompt) {
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      sheet.close();
    }
  });
  icons();
  sheet.open();
}

/** Muestra el aviso una vez (en celulares, si no está instalada ni lo cerraron hace poco). */
export function maybeSuggestInstall() {
  if (isInstalled()) return;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();          // que no salga el cartel del navegador: usamos el nuestro
    deferredPrompt = e;
    if (!snoozed()) setTimeout(openInstall, 2500);
  });
  const mobile = matchMedia("(max-width: 767px)").matches;
  if (isIOS() && mobile && !snoozed()) setTimeout(openInstall, 2500);
}
