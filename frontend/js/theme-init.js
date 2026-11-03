// Se carga en el <head> ANTES de dibujar la página, para que no "parpadee"
// en el tema equivocado. Por defecto es oscuro; si el usuario eligió claro
// con el botón, lo recordamos.
(function () {
  var saved = null;
  try { saved = localStorage.getItem("vb-theme"); } catch (e) { /* sin almacenamiento */ }
  document.documentElement.dataset.theme = saved === "light" ? "light" : "dark";
})();

// App instalable (PWA): registramos el service worker (sw.js). Es lo que
// permite "Agregar a inicio" y abrir aunque no haya señal.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js").catch(function () { /* sin PWA: la web sigue andando igual */ });
  });
}
