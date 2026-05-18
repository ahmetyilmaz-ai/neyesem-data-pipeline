from pathlib import Path

path = Path("scrapers/trendyol_scraper.py")
text = path.read_text(encoding="utf-8")

old = '''    print("Sayfa açıldı. Cookie/konum ekranı varsa tarayıcıda hallet.")
    input("Hazır olunca Enter'a bas: ")

    scroll_page(page)
'''

new = '''    print("Sayfa açıldı. Otomatik bekleme ve scroll başlıyor.")
    page.wait_for_timeout(3000)

    scroll_page(page)
'''

if old not in text:
    raise RuntimeError("Beklenen Enter bloğu bulunamadı. trendyol_scraper.py değişmiş olabilir.")

text = text.replace(old, new)
path.write_text(text, encoding="utf-8")

print("Trendyol scraper artık Enter beklemiyor.")
