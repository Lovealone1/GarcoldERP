from typing import Optional, Dict, Any
import os, sys, asyncio, logging, time, tempfile, re, subprocess, glob
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright  # sigue siendo el plan A
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

    # -------------------- helpers --------------------

    def _find_system_chromium(self) -> Optional[str]:
        # 1) override por env
        env_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or os.environ.get("CHROME_BIN")
        if env_path and Path(env_path).exists():
            return env_path
        # 2) PATH estándar
        for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
            p = which(name)
            if p:
                return p
        # 3) ruta Nix: /nix/store/<hash>-chromium-*/bin/chromium
        candidates = sorted(glob.glob("/nix/store/*-chromium-*/bin/chromium"))
        for p in candidates:
            if Path(p).exists():
                return p
        # 4) otras rutas comunes
        for p in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
            if Path(p).exists():
                return p
        return None

    def _render_via_cli(self, url: str) -> bytes:
        chrome = self._find_system_chromium()
        if not chrome:
            raise RuntimeError("Chromium no encontrado para fallback CLI.")
        tmp_pdf = TMP_DIR / f"invoice_cli_{int(time.time())}.pdf"
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            f"--print-to-pdf={str(tmp_pdf)}",
            "--print-to-pdf-no-header",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=10000",
            url,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        if res.returncode != 0 or not tmp_pdf.exists():
            raise RuntimeError(f"Chromium CLI falló. rc={res.returncode} stderr={res.stderr.decode(errors='ignore')[:400]}")
        try:
            return tmp_pdf.read_bytes()
        finally:
            try: tmp_pdf.unlink(missing_ok=True)
            except Exception: pass

    # -------------------- público --------------------

    async def render_invoice_pdf(
        self,
        sale_id: int,
        path: str = "/comercial/ventas/facturas/{sale_id}",
        pdf_options: Optional[Dict[str, Any]] = None,
        extra_query: str = "print=1",  # tu UI debe aplicar @media print
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
            "margin": {"top": f"{top_mm}mm","right": f"{right_mm}mm","bottom": f"{bottom_mm}mm","left": f"{left_mm}mm"},
            "scale": 1,
        }
        if pdf_options:
            base_opts.update(pdf_options)

        CSS = f"""
        @page {{ size: 210mm 297mm; margin: 0; }}
        @media print {{
          html, body {{ width: 210mm !important; height: auto !important; margin:0; padding:0; }}
          body {{ box-sizing:border-box !important; padding:{top_mm:.2f}mm {right_mm:.2f}mm {bottom_mm:.2f}mm {left_mm:.2f}mm !important; background:#fff !important; }}
          #invoice-root, .invoice-root, [data-invoice-root], main, #__next > div:first-child {{
            box-sizing:border-box !important; width:auto !important;
            max-width: calc(210mm - {left_mm:.2f}mm - {right_mm:.2f}mm) !important;
            margin:0 !important; padding:0 !important; height:auto !important; min-height:0 !important; page-break-inside:avoid !important;
          }}
          * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} .no-print {{ display:none !important; }}
        }}
        """

        def _do_sync() -> bytes:
            # Plan A: Playwright si hay navegador utilizable
            try:
                from playwright.sync_api import Browser  # type: ignore
                with sync_playwright() as p:
                    # Intento 1: Chromium sistema con Playwright
                    exec_path = self._find_system_chromium()
                    if exec_path:
                        try:
                            browser = p.chromium.launch(headless=True, executable_path=exec_path,
                                                        args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"])
                        except Exception:
                            browser = None
                    else:
                        browser = None
                    # Intento 2: bundle de Playwright
                    if browser is None:
                        browser = p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"])
                    ctx = browser.new_context(locale="es-CO")
                    try:
                        page = ctx.new_page()
                        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                        page.add_style_tag(content=CSS)
                        try: page.wait_for_function("window.__PRINT_READY__ === true", timeout=5_000)
                        except Exception: page.wait_for_timeout(1500)
                        page.emulate_media(media="print")
                        opts = {"format":"A4","print_background":True,"prefer_css_page_size":True,"margin":{"top":"0","right":"0","bottom":"0","left":"0"},"scale":1}
                        pdf_all = page.pdf(**opts)
                        try:
                            pages = len(re.findall(rb"/Type\s*/Page\b", pdf_all or b""))
                        except Exception:
                            pages = 0
                        if pages >= 2 and "page_ranges" not in opts:
                            try:
                                return page.pdf(**{**opts, "page_ranges":"1"})
                            except Exception:
                                pass
                        return pdf_all
                    finally:
                        try: ctx.close()
                        except Exception: pass
                        try: browser.close()
                        except Exception: pass
            except Exception as e:
                log.warning("[PdfRenderer] Playwright no disponible (%s). Uso fallback CLI.", e)

            # Plan B: Chromium CLI
            return self._render_via_cli(url)

        return await asyncio.to_thread(_do_sync)
