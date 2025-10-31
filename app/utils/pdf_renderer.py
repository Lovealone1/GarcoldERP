from typing import Optional, Dict, Any
import os
import sys
import asyncio
import logging
import time
import tempfile
import re
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright, Browser  
from app.core.settings import settings

log = logging.getLogger("pdf")
TMP_DIR = Path(tempfile.gettempdir())

if sys.platform == "win32" and not isinstance(
    asyncio.get_event_loop_policy(), getattr(asyncio, "WindowsProactorEventLoopPolicy")
):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

class PdfRenderer:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or settings.FRONTEND_URL).rstrip("/")

    # ---- helpers -------------------------------------------------------------

    def _find_system_chromium(self) -> Optional[str]:
        """
        Busca un ejecutable de Chromium del sistema.
        Orden:
          1) PLAYWRIGHT_CHROMIUM_EXECUTABLE (override explícito)
          2) which('chromium') / which('chromium-browser')
          3) rutas comunes en Linux
        """
        env_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        if env_path and Path(env_path).exists():
            return env_path

        for name in ("chromium", "chromium-browser", "google-chrome", "chrome", "chromium-headless"):
            p = which(name)
            if p:
                return p

        # Rutas típicas (por si which no encuentra en PATH)
        for p in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
            if Path(p).exists():
                return p

        return None

    def _launch_browser(self, p) -> "Browser":
        """
        Lanza Chromium con preferencia por el del sistema.
        Si no existe, intenta el bundle de Playwright.
        Lanza excepción con mensaje útil si nada funciona.
        """
        # flags necesarios en contenedores
        args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]

        # 1) Intentar con Chromium del sistema
        sys_exec = self._find_system_chromium()
        if sys_exec:
            try:
                log.info("[PdfRenderer] Launching system Chromium at %s", sys_exec)
                return p.chromium.launch(headless=True, executable_path=sys_exec, args=args)
            except Exception as e:
                log.warning("[PdfRenderer] System Chromium failed (%s). Will try Playwright bundle.", e)

        # 2) Intentar con el bundle de Playwright (PLAYWRIGHT_BROWSERS_PATH o cache por defecto)
        try:
            bundle_root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "~/.cache/ms-playwright"
            log.info("[PdfRenderer] Launching Playwright-bundled Chromium (BROWSERS_PATH=%s)", bundle_root)
            return p.chromium.launch(headless=True, args=args)
        except Exception as e:
            hint = (
                "Ningún Chromium disponible. Opciones:\n"
                " - En Nixpacks añade 'chromium' a [phases.setup].nixPkgs y reinicia.\n"
                " - O usa imagen base de Playwright (Docker) o instala browsers en build.\n"
                " - O define PLAYWRIGHT_CHROMIUM_EXECUTABLE apuntando a un binario válido."
            )
            raise RuntimeError(f"Fallo lanzando Chromium (system y bundle). {hint}\nCausa: {e}") from e

    # ---- público ------------------------------------------------------------

    async def render_invoice_pdf(
        self,
        sale_id: int,
        path: str = "/comercial/ventas/facturas/{sale_id}",
        pdf_options: Optional[Dict[str, Any]] = None,
        extra_query: str = "print=1",
        left_mm: float = 22.0,
        right_mm: float = 0.0,
        top_mm: float = 0.0,
        bottom_mm: float = 0.0,
    ) -> bytes:
        url = f"{self.base_url}{path.format(sale_id=sale_id)}"
        if extra_query:
            url += ("&" if "?" in url else "?") + extra_query

        base_opts: Dict[str, Any] = {
            "print_background": True,
            "prefer_css_page_size": True,
            "margin": {
                "top": f"{top_mm}mm",
                "right": f"{right_mm}mm",
                "bottom": f"{bottom_mm}mm",
                "left": f"{left_mm}mm",
            },
            "scale": 1,
        }
        if pdf_options:
            base_opts.update(pdf_options)

        def _do_sync() -> bytes:
            CSS = f"""
            @page {{ size: 210mm 297mm; margin: 0; }}

            @media print {{
            html, body {{
                width: 210mm !important;
                height: auto !important;
                min-height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
            }}

            body {{
                box-sizing: border-box !important;
                padding: {top_mm:.2f}mm {right_mm:.2f}mm {bottom_mm:.2f}mm {left_mm:.2f}mm !important;
                background: #ffffff !important;
            }}

            #invoice-root, .invoice-root, [data-invoice-root], main, #__next > div:first-child {{
                box-sizing: border-box !important;
                width: auto !important;
                max-width: calc(210mm - {left_mm:.2f}mm - {right_mm:.2f}mm) !important;
                margin: 0 !important;
                padding: 0 !important;
                height: auto !important;
                min-height: 0 !important;
                page-break-inside: avoid !important;
            }}

            * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            .no-print {{ display: none !important; }}
            }}
            """

            browser = None
            ctx = None
            try:
                with sync_playwright() as pw:
                    browser = self._launch_browser(pw)
                    ctx = browser.new_context(locale="es-CO")
                    page = ctx.new_page()

                    # Carga y espera lo mínimo para imprimir
                    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                    page.add_style_tag(content=CSS)

                    # Señal opcional de tu UI para "listo para imprimir"
                    try:
                        page.wait_for_function("window.__PRINT_READY__ === true", timeout=5_000)
                    except Exception:
                        page.wait_for_timeout(1500)

                    page.emulate_media(media="print")

                    opts = {
                        "format": "A4",
                        "print_background": True,
                        "prefer_css_page_size": True,
                        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
                        "scale": 1,
                    }
                    pdf_all = page.pdf(**opts)

                    # Si detecta 2+ páginas y no pediste rango, devuelve solo la 1
                    try:
                        pages = len(re.findall(rb"/Type\s*/Page\b", pdf_all or b""))
                    except Exception:
                        pages = 0
                    if pages >= 2 and "page_ranges" not in opts:
                        try:
                            return page.pdf(**{**opts, "page_ranges": "1"})
                        except Exception:
                            pass

                    return pdf_all
            except Exception as e:
                ts = int(time.time())
                img = TMP_DIR / f"pdf_fail_{sale_id}_{ts}.png"
                html = TMP_DIR / f"pdf_fail_{sale_id}_{ts}.html"
                try:
                    # Sólo si page/context existen
                    if ctx:
                        try:
                            # intenta capturar screenshot desde la página activa
                            for p in ctx.pages:
                                try:
                                    p.screenshot(path=str(img), full_page=True)
                                    break
                                except Exception:
                                    continue
                        except Exception:
                            pass
                        try:
                            for p in ctx.pages:
                                try:
                                    html.write_text(p.content(), encoding="utf-8")
                                    break
                                except Exception:
                                    continue
                        except Exception:
                            pass
                finally:
                    log.error("PDF error url=%s screenshot=%s html=%s err=%r", url, img, html, e)
                raise
            finally:
                try:
                    if ctx:
                        ctx.close()
                except Exception:
                    pass
                try:
                    if browser:
                        browser.close()
                except Exception:
                    pass

        return await asyncio.to_thread(_do_sync)
