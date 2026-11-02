// =========================================================================
// labels.js · Traducción de los valores técnicos de la API al español.
// La API dice "monthly"; el usuario ve "Mensual".
// =========================================================================

import { api } from "./api.js";

export const FREQUENCY = {
  weekly: "Semanal", biweekly: "Quincenal", monthly: "Mensual", annual: "Anual", one_time: "Única vez",
};
export const KIND = {
  variable: "Del día a día",
  one_off: "Puntual (no es habitual)",
  fixed: "Fijo (todos los meses)",
};
export const PRIORITY = { high: "Alta", medium: "Media", low: "Baja" };
export const SUB_FREQUENCY = { monthly: "Mensual", annual: "Anual" };

// Colores por categoría (tokens de app.css), para íconos y gráficos
// (Vivienda suele ser lo más grande: le damos el celeste de la marca)
export const CATEGORY_COLOR = {
  housing: "--cat-1", food: "--cat-2", utilities: "--cat-6", transport: "--cat-4",
  leisure: "--cat-5", health: "--cat-3", personal_care: "--cat-5", education: "--cat-4",
  clothing: "--cat-3", tech: "--cat-3", pets: "--cat-6", gifts: "--cat-5",
  finance: "--cat-7", other: "--cat-7", subscriptions: "--cat-3", variable_estimate: "--cat-7",
};

// El árbol de categorías viene del backend (/api/categories) — única fuente
// de verdad. Lo pedimos una vez y lo guardamos en memoria.
let categoriesPromise;
export function getCategories() {
  categoriesPromise ??= api("/api/categories").then((list) => {
    const byKey = Object.fromEntries(list.map((c) => [c.key, c]));
    return { list, byKey };
  });
  return categoriesPromise;
}

/** "food" + "snacks" -> "Comida · Kiosco y antojos" */
export function categoryLabel(cats, category, subcategory) {
  const cat = cats.byKey[category];
  if (!cat) return category;
  const sub = cat.subcategories.find((s) => s.key === subcategory);
  return sub ? `${cat.label} · ${sub.label}` : cat.label;
}

// Nombres extra para el gráfico de categorías del dashboard
export const EXTRA_CATEGORY_LABELS = { subscriptions: "Suscripciones", variable_estimate: "Gastos variables (estimado)" };
