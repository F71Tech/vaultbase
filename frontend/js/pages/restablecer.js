// restablecer.js · Elegir una contraseña nueva con el link que generó el administrador.

import { api } from "../api.js";
import { icons } from "../ui.js";

const $ = (id) => document.getElementById(id);
const token = new URLSearchParams(location.search).get("token");

if (!token) {
  $("subtitle").textContent = "Este link está incompleto. Pedí uno nuevo.";
  $("reset-form").hidden = true;
}

$("reset-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pass = $("pass").value;
  if (pass.length < 8) return ($("error").textContent = "Tiene que tener al menos 8 caracteres.");
  if (pass !== $("pass2").value) return ($("error").textContent = "Las dos contraseñas no coinciden.");
  $("submit").disabled = true;
  try {
    await api("/api/auth/reset", { method: "POST", body: { token, new_password: pass } });
    $("reset-form").hidden = true;
    $("subtitle").hidden = true;
    $("done").hidden = false;
    icons();
  } catch (err) {
    $("error").textContent = err.message;
  } finally {
    $("submit").disabled = false;
  }
});

icons();
