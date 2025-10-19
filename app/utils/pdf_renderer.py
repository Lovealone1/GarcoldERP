from typing import Optional, Dict, Any
import sys
import asyncio
import logging
import time
import tempfile
import re
from pathlib import Path

from playwright.sync_api import sync_playwright
from app.core.settings import settings

log = logging.getLogger("pdf")
TMP_DIR = Path(tempfile.gettempdir())

# Windows: usar Proactor para permitir Chromium + threads
if sys.platform == "win32" and not isinstance(
    asyncio.get_event_loop_policy(), getattr(asyncio, "WindowsProactorEventLoopPolicy")
):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

class PdfRenderer:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or settings.FRONTEND_URL).rstrip("/")

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

        content_mm = max(0.0, 210.0)

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

            /* Desplazamiento y márgenes físicos con padding del body */
            body {{
                box-sizing: border-box !important;
                padding: {top_mm:.2f}mm {right_mm:.2f}mm {bottom_mm:.2f}mm {left_mm:.2f}mm !important;
                background: #ffffff !important;
            }}

            /* Asegura que cualquier wrapper no exceda el ancho útil */
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

            /* Evita overflow vertical que crea página extra */
            * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            .no-print {{ display: none !important; }}
            }}
            """

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                ctx = browser.new_context(locale="es-CO")
                page = ctx.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60_000)

                    page.add_style_tag(content=CSS)

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
                        try: page.screenshot(path=str(img), full_page=True)
                        except Exception: pass
                        try: html.write_text(page.content(), encoding="utf-8")
                        except Exception: pass
                        log.error("PDF error url=%s screenshot=%s html=%s err=%r", url, img, html, e)
                    finally:
                        try: ctx.close()
                        finally: browser.close()
                    raise
                finally:
                    try: ctx.close()
                    except Exception: pass
                    try: browser.close()
                    except Exception: pass



        return await asyncio.to_thread(_do_sync)
