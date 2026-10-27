"""Captura telas reais dos aplicativos publicados, para documentação do portfólio."""
from pathlib import Path
from playwright.sync_api import sync_playwright

APPS = {
    "bazinbot": ("https://bazinbot.onrender.com/", "BazinBot"),
    "chatbot": ("https://chatbot-financeiro-9p1s.onrender.com/", "Chatbot Financeiro"),
    "fotoimagem": ("https://fotoimagem.onrender.com/", "FotoImagem"),
}

OUTPUT = Path("assets/screenshots")
OUTPUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    for name, (url, label) in APPS.items():
        print(f"Abrindo {label}: {url}", flush=True)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=180000)
            page.locator('[data-testid="stAppViewContainer"]').wait_for(timeout=180000)
            # Streamlit pode renderizar o conteúdo após o DOM inicial do navegador.
            # Não publicar capturas de splash/loading como se fossem interfaces prontas.
            expected = label.lower().split()[0]
            try:
                page.wait_for_function(
                    "needle => document.body.innerText.toLowerCase().includes(needle)",
                    expected,
                    timeout=110000,
                )
            except Exception:
                body = page.locator("body").inner_text(timeout=15000)
                raise RuntimeError(f"Conteúdo esperado '{expected}' não carregou: {body[:220]}")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(OUTPUT / f"{name}.png"), full_page=True, animations="disabled")
            print(f"Captura realizada: {name}.png", flush=True)
        except Exception as exc:
            print(f"Não foi possível capturar {name}: {exc}", flush=True)
    browser.close()
