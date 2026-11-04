// =========================================================================
// refresh.js · Mantener los números al día.
//
// 1) "Deslizá hacia abajo para actualizar" (como en Instagram o WhatsApp).
//    Solo en la app INSTALADA: ahí no hay barra del navegador ni botón de
//    recargar. En el navegador común ese gesto ya lo trae el propio navegador.
// 2) Si volvés a la app después de un rato, los datos se vuelven a pedir solos.
// =========================================================================

import { isInstalled } from "./install.js";
import { icons, notifyDataChanged } from "./ui.js";

const PULL_TO_REFRESH = 80;      // píxeles que hay que tirar para que actualice
const STALE_MS = 2 * 60 * 1000;  // más de 2 minutos afuera = datos viejos

// ¿Hay algo abierto encima (una hoja, el tutorial)? Entonces el gesto no hace nada.
const busy = () => document.documentElement.classList.contains("tour-open")
  || document.querySelector(".sheet-open");

function setupPull() {
  const pill = document.createElement("div");
  pill.className = "ptr";
  pill.innerHTML = `<i data-lucide="refresh-cw" class="w-5 h-5"></i>`;
  document.body.append(pill);
  icons();

  let startY = null;
  let dy = 0;
  addEventListener("touchstart", (e) => {
    // Solo si estás arriba de todo de la pantalla (en el celular scrollea .app-layout, no la página)
    const scrolled = scrollY + (document.querySelector(".app-layout")?.scrollTop || 0);
    startY = scrolled <= 0 && !busy() ? e.touches[0].clientY : null;
    dy = 0;
  }, { passive: true });
  addEventListener("touchmove", (e) => {
    if (startY === null) return;
    dy = Math.max(0, e.touches[0].clientY - startY);
    const pull = Math.min(dy, PULL_TO_REFRESH * 1.5);
    pill.style.transition = "none";  // mientras arrastrás, sigue al dedo al instante (sin animación que la atrase)
    // La bolita baja con el dedo y el ícono gira; al llegar al límite se "enciende"
    pill.style.transform = `translate(-50%, ${pull - 56}px) rotate(${pull * 3}deg)`;
    pill.classList.toggle("ready", dy >= PULL_TO_REFRESH);
  }, { passive: true });
  addEventListener("touchend", () => {
    if (startY === null) return;
    startY = null;
    pill.style.transition = "";  // al soltar, vuelve con animación suave
    if (dy >= PULL_TO_REFRESH) {
      pill.classList.add("spinning");
      pill.style.transform = "translate(-50%, 24px)";
      location.reload();  // recarga todo: datos nuevos y, si hubo, la versión nueva de la app
    } else {
      pill.style.transform = "";
      pill.classList.remove("ready");
    }
  });
}

function setupAutoRefresh() {
  let hiddenAt = 0;
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) hiddenAt = Date.now();
    else if (hiddenAt && Date.now() - hiddenAt > STALE_MS) notifyDataChanged();  // cada pantalla recarga sus datos
  });
}

export function setupRefresh() {
  if (isInstalled()) setupPull();
  setupAutoRefresh();
}
