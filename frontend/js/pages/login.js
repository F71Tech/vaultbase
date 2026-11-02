// login.js · Pantalla de ingreso y registro.

import { api, auth, startDemo } from "../api.js";
import { icons } from "../ui.js";

const form = document.getElementById("auth-form");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit");
let mode = new URLSearchParams(location.search).get("mode") === "register" ? "register" : "login";

const TEXTS = {
  login: { title: "¡Hola de nuevo!", subtitle: "Ingresá para ver tus finanzas.", button: "Ingresar" },
  register: { title: "Creá tu cuenta", subtitle: "Es gratis y te lleva un minuto.", button: "Crear cuenta" },
};

function setMode(next) {
  mode = next;
  document.querySelectorAll("[data-mode]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.mode === mode));
  document.getElementById("name-field").hidden = mode !== "register";
  document.getElementById("title").textContent = TEXTS[mode].title;
  document.getElementById("subtitle").textContent = TEXTS[mode].subtitle;
  submitBtn.textContent = TEXTS[mode].button;
  form.password.autocomplete = mode === "register" ? "new-password" : "current-password";
  errorEl.textContent = "";
}

// A dónde volver después de ingresar. Solo aceptamos rutas internas ("/algo"),
// nunca otra web: si no, alguien podría mandarte un link que te redirija a
// una página falsa después de loguearte (ataque de "open redirect").
function nextPage() {
  const next = new URLSearchParams(location.search).get("next");
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard.html";
}

async function onSubmit(event) {
  event.preventDefault();
  errorEl.textContent = "";
  const email = form.email.value.trim();
  const password = form.password.value;
  // Ojo: form.name sería el atributo "name" del propio <form>, no el campo.
  const name = form.elements.namedItem("name").value.trim();

  // Validación rápida en el navegador (el servidor igual vuelve a validar)
  if (mode === "register" && !name) return (errorEl.textContent = "Contanos tu nombre.");
  if (!email.includes("@")) return (errorEl.textContent = "Revisá el email.");
  if (password.length < 8) return (errorEl.textContent = "La contraseña debe tener al menos 8 caracteres.");

  submitBtn.disabled = true;
  try {
    if (mode === "register") {
      await api("/api/auth/register", { method: "POST", body: { name, email, password } });
    }
    const { access_token } = await api("/api/auth/login", {
      method: "POST", form: { username: email, password },
    });
    auth.save(access_token);
    location.href = nextPage();
  } catch (err) {
    errorEl.textContent = err.message;
    submitBtn.disabled = false;
  }
}

document.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
document.getElementById("toggle-pass").addEventListener("click", () => {
  form.password.type = form.password.type === "password" ? "text" : "password";
});
form.addEventListener("submit", onSubmit);
const demoBtn = document.getElementById("demo-btn");
demoBtn.addEventListener("click", async () => {
  demoBtn.disabled = true;
  demoBtn.lastChild.textContent = "Preparando la demo…";
  try {
    await startDemo();
  } catch (err) {
    errorEl.textContent = err.message;
    demoBtn.disabled = false;
    demoBtn.lastChild.textContent = "Probar la demo sin registrarme";
  }
});

if (auth.loggedIn) location.replace(nextPage());
setMode(mode);
icons();
