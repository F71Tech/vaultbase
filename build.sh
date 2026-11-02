#!/usr/bin/env bash
# Comandos que Render ejecuta para "construir" la app antes de arrancarla.
# (Es un script de bash porque los servidores de Render son Linux.)
set -o errexit  # si un comando falla, se corta el build

# 1) Instalar las librerías de Python
pip install -r requirements.txt

# 2) Bajar el compilador oficial de Tailwind (la misma versión que el CDN).
#    Si falla la descarga, seguimos igual: la app usará el CDN.
TAILWIND_URL="https://github.com/tailwindlabs/tailwindcss/releases/download/v4.1.11/tailwindcss-linux-x64"
if curl -sSfLo tailwindcss "$TAILWIND_URL"; then
  chmod +x tailwindcss
  python scripts/build_frontend.py ./tailwindcss
else
  echo "[build] No se pudo descargar Tailwind; se usará el CDN."
fi
