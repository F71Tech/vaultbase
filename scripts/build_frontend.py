"""
Prepara el frontend para producción (lo ejecuta build.sh en Render).

1. Compila Tailwind con el ejecutable oficial -> frontend/css/tailwind.css
   (un archivo chico, solo con las clases que usamos).
2. En cada HTML, cambia el <script> del CDN de Tailwind (que compila EN el
   navegador, más lento) por un <link> a ese archivo ya compilado.

Si el paso 1 falla, NO toca los HTML: la app sigue funcionando con el CDN.
En tu PC no hace falta correr esto: el CDN es más cómodo para desarrollar.

Uso:  python scripts/build_frontend.py ./tailwindcss
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
CDN_TAG = '<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4.1.11"></script>'
LINK_TAG = '<link rel="stylesheet" href="/css/tailwind.css" />'


def compile_tailwind(binary: str) -> bool:
    output = FRONTEND / "css" / "tailwind.css"
    try:
        subprocess.run(
            [binary, "-i", str(FRONTEND / "css" / "tailwind.src.css"), "-o", str(output), "--minify"],
            cwd=FRONTEND, check=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as error:
        print(f"[build] No se pudo compilar Tailwind ({error}). Se mantiene el CDN.")
        return False
    if not output.exists() or output.stat().st_size < 1000:
        print("[build] El CSS compilado salió vacío. Se mantiene el CDN.")
        return False
    print(f"[build] Tailwind compilado: {output.stat().st_size // 1024} KB")
    return True


def swap_cdn_for_compiled_css() -> int:
    changed = 0
    for page in FRONTEND.glob("*.html"):
        html = page.read_text(encoding="utf-8")
        if CDN_TAG in html:
            page.write_text(html.replace(CDN_TAG, LINK_TAG), encoding="utf-8")
            changed += 1
    print(f"[build] {changed} páginas ahora usan el CSS compilado")
    return changed


if __name__ == "__main__":
    if len(sys.argv) > 1 and compile_tailwind(sys.argv[1]):
        swap_cdn_for_compiled_css()
