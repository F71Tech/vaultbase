// Se carga en el <head> ANTES de dibujar la página, para que no "parpadee"
// en el tema equivocado. Por defecto es oscuro; si el usuario eligió claro
// con el botón, lo recordamos.
(function () {
  var saved = null;
  try { saved = localStorage.getItem("vb-theme"); } catch (e) { /* sin almacenamiento */ }
  document.documentElement.dataset.theme = saved === "light" ? "light" : "dark";
})();
