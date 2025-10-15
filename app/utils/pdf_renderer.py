from typing import Optional, Dict, Any
import sys, asyncio, logging, time, tempfile, re
from pathlib import Path
from playwright.sync_api import sync_playwright
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

    async def render_invoice_pdf(
        self,
        sale_id: int,
        path: str = "/comercial/ventas/facturas/{sale_id}",
        pdf_options: Optional[Dict[str, Any]] = None,
        extra_query: str = "print=1",
    ) -> bytes:
        url = f"{self.base_url}{path.format(sale_id=sale_id)}"
        if extra_query:
            url += ("&" if "?" in url else "?") + extra_query

        opts: Dict[str, Any] = {
            "format": "A4",
            "print_background": True,
            "prefer_css_page_size": True,
            "margin": {"top": "0", "right": "100mm", "bottom": "10mm", "left": "0"},
        }
        if pdf_options:
            opts.update(pdf_options)

        def _do_sync() -> bytes:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                ctx = browser.new_context(locale="es-CO")
                page = ctx.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                    try:
                        page.wait_for_function("window.__PRINT_READY__ === true", timeout=5_000)
                    except Exception:
                        page.wait_for_timeout(1500)
                    page.emulate_media(media="print")

                    pdf_all = page.pdf(**opts)
                    pages = len(re.findall(rb"/Type\s*/Page\b", pdf_all or b""))
                    if pages >= 3 and "page_ranges" not in opts:
                        try:
                            ranges = f"2-{pages-1}"
                            return page.pdf(**{**opts, "page_ranges": ranges})
                        except Exception:
                            return pdf_all
                    return pdf_all
                except Exception as e:
                    ts = int(time.time())
                    img = TMP_DIR / f"pdf_fail_{sale_id}_{ts}.png"
                    html = TMP_DIR / f"pdf_fail_{sale_id}_{ts}.html"
                    try:
                        page.screenshot(path=str(img), full_page=True)
                        html.write_text(page.content(), encoding="utf-8")
                        log.error("PDF error url=%s screenshot=%s html=%s err=%r", url, img, html, e)
                    finally:
                        ctx.close()
                        browser.close()
                    raise
                finally:
                    if not page.is_closed():
                        ctx.close()
                        browser.close()

        return await asyncio.to_thread(_do_sync)
