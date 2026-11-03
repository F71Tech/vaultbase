"""Test del script que prepara el frontend para producción."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_frontend", ROOT / "scripts" / "build_frontend.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_todas_las_paginas_tienen_el_cdn_esperado():
    # Si alguien cambia la versión del CDN en un HTML y no en el script,
    # esa página quedaría sin el CSS compilado en producción.
    # (offline.html no usa Tailwind: se ve sin internet, con sus propios estilos)
    for page in (ROOT / "frontend").glob("*.html"):
        if page.name == "offline.html":
            continue
        assert build.CDN_TAG in page.read_text(encoding="utf-8"), page.name


def test_app_instalable():
    # Cada página tiene lo necesario para "Agregar a inicio" (PWA)
    for page in (ROOT / "frontend").glob("*.html"):
        if page.name == "offline.html":
            continue
        html = page.read_text(encoding="utf-8")
        assert 'rel="manifest"' in html and "apple-touch-icon" in html, page.name
    for icon in ("icon-192.png", "icon-512.png", "apple-touch-icon.png"):
        assert (ROOT / "frontend" / "icons" / icon).exists()
    assert (ROOT / "frontend" / "sw.js").exists()


def test_reemplaza_cdn_por_css_compilado(tmp_path, monkeypatch):
    page = tmp_path / "x.html"
    page.write_text(f"<head>{build.CDN_TAG}</head>", encoding="utf-8")
    monkeypatch.setattr(build, "FRONTEND", tmp_path)
    assert build.swap_cdn_for_compiled_css() == 1
    assert build.LINK_TAG in page.read_text(encoding="utf-8")


def test_el_compilador_se_llama_con_ruta_absoluta(tmp_path, monkeypatch):
    # Bug real del primer deploy: "./tailwindcss" se buscaba dentro de frontend/
    llamadas = []
    monkeypatch.setattr(build, "FRONTEND", tmp_path)
    monkeypatch.setattr(build.subprocess, "run", lambda args, **kw: llamadas.append((args, kw)))
    build.compile_tailwind("./tailwindcss")
    args, kw = llamadas[0]
    assert Path(args[0]).is_absolute()
    assert kw["cwd"] == tmp_path


def test_si_no_hay_compilador_no_toca_nada(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "FRONTEND", tmp_path)
    assert build.compile_tailwind(str(tmp_path / "no-existe")) is False
