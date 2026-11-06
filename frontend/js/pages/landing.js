// landing.js · Portada: botones de demo y animaciones al hacer scroll.

import { startDemo } from "../api.js";
import { money } from "../format.js";
import { countUp, reducedMotion } from "../ui.js";

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// --- Probar la demo (hay un botón arriba y otro al final) ---
document.querySelectorAll("[data-demo]").forEach((btn) => {
  const label = btn.lastChild.textContent;
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.lastChild.textContent = "Preparando la demo…";
    try { await startDemo(); } catch { btn.disabled = false; btn.lastChild.textContent = label; }
  });
});

// --- Lo que pasa en cada dibujo de la app cuando entra en pantalla ---
function countAll(root) {
  root.querySelectorAll("[data-count]").forEach((el) => countUp(el, Number(el.dataset.count) * 100));
}

/** Gasto rápido: se "escribe" el monto, se elige la categoría y se guarda. */
async function playExpense(root) {
  const amount = root.querySelector("[data-typing]");
  const plata = root.querySelector("[data-plata]");
  await wait(600);
  for (const text of ["$ 1", "$ 18", "$ 180"]) {
    amount.textContent = text;
    await wait(320);
  }
  root.querySelector(".mock-cat[data-pick]").classList.add("on");
  await wait(650);
  root.classList.add("pressing");
  await wait(180);
  root.classList.remove("pressing");
  root.classList.add("saved");
  plata.dataset.value = 1634000;  // countUp arranca desde acá y baja hasta el nuevo número
  countUp(plata, 1616000);
}

const PLAYS = { count: countAll, expense: playExpense };

function play(root) {
  const story = root.dataset.story;
  if (story) PLAYS[story]?.(root);
}

// La barra de la portada y su número arrancan apenas abre la página
countAll(document.querySelector("[data-hero]"));
requestAnimationFrame(() => setTimeout(() => {
  document.querySelector("[data-hero] [data-fill]").style.width = `${document.querySelector("[data-hero] [data-fill]").dataset.fill}%`;
}, 200));

document.getElementById("year").textContent = new Date().getFullYear();

// --- Aparecer al llegar con el scroll ---
const targets = document.querySelectorAll(".reveal, .step-line");
if (reducedMotion() || !("IntersectionObserver" in window)) {
  targets.forEach((el) => el.classList.add("in"));
  document.querySelectorAll("[data-story]").forEach((el) => {
    if (el.dataset.story === "expense") {
      el.querySelector("[data-typing]").textContent = "$ 180";
      el.querySelector(".mock-cat[data-pick]").classList.add("on");
      el.querySelector("[data-plata]").textContent = money(1616000);
      el.classList.add("saved");
    }
  });
} else {
  // Recién acá escondemos: sin JavaScript la página se ve completa igual
  document.documentElement.classList.add("js-reveal");
  const seen = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("in");
      play(entry.target);
      seen.unobserve(entry.target);
    });
  }, { threshold: 0.15, rootMargin: "0px 0px -6% 0px" });
  targets.forEach((el) => seen.observe(el));
}
