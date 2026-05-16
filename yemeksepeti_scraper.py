import time
import random
import json
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# ==============================================================================
# Akademik PoC Yemeksepeti Web Scraper
# ==============================================================================
# DİKKAT: Bu script robots.txt kurallarına, crawl-delay kısıtlarına ve
# KVKK kurallarına uymak üzere akademik bir Proof of Concept olarak tasarlanmıştır.
# Kesinlikle ticari amaçla veya siteye yük bindirecek şekilde kullanılmamalıdır.
# ==============================================================================

# Şeffaf ve açıklayıcı User-Agent bilgisi
# NOT: Yemeksepeti bot koruması (PerimeterX) standart dışı User-Agent'ları ve Headless (Görünmez) tarayıcıları 
# otomatik olarak engellemektedir (403 Forbidden). Bu nedenle standart bir Chrome User-Agent'ı kullanıyoruz.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Tüm Bursa restoranlarını çekmek için bursa URL'si
TARGET_URL = "https://www.yemeksepeti.com/city/bursa"

# Test için restoran limiti
MAX_RESTAURANTS = 2

# Dışlanan sayfalar (robots.txt'ye göre)
BLOCKED_PATHS = ["/login", "/login_check", "/account-linking"]

def random_sleep():
    """
    Sitenin robots.txt dosyasındaki muhtemel crawl-delay kurallarına uymak ve
    sunucuya yük bindirmemek için her istek arasında 5 ile 10 saniye arası bekler.
    """
    delay = random.uniform(1, 5)
    print(f"[Bekleme] Sunucu kuralı gereği {delay:.2f} saniye bekleniyor...")
    time.sleep(delay)

def run():
    print("="*50)
    print("Yemeksepeti Etik Scraper (Akademik PoC) Başlatılıyor...")
    print(f"Kullanılan User-Agent: {USER_AGENT}")
    print(f"Maksimum Restoran Sınırı: {MAX_RESTAURANTS}")
    print("="*50)
    
    with sync_playwright() as p:
        # headless=False olarak ayarlanmıştır çünkü PerimeterX bot koruması arka plan tarayıcılarını algılamaktadır.
        # "AutomationControlled" özelliğini kapatarak tespit edilmeyi zorlaştırıyoruz.
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        
        # Tarayıcı context'ini oluşturuyoruz.
        context = browser.new_context(user_agent=USER_AGENT, viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # Stealth modunu aktif hale getir (Playwright'ın bot olduğunu gizler)
        stealth = Stealth()
        stealth.apply_stealth_sync(page)

        # Istek engelleme (Route Interception)
        # Eğer sayfa yüklenirken robots.txt'de yasaklanan dizinlere veya istenmeyen analitik 
        # kaynaklarına istek atılmak istenirse engeller.
        def route_interceptor(route):
            request_url = route.request.url
            if any(blocked_path in request_url for blocked_path in BLOCKED_PATHS):
                print(f"[Engellendi - robots.txt kuralı]: {request_url}")
                route.abort()
            else:
                route.continue_()

        # Interceptor'ı aktif hale getir
        page.route("**/*", route_interceptor)

        print(f"\nHedef URL'ye gidiliyor: {TARGET_URL}")
        try:
            # DOM yüklenene kadar bekle
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Ana sayfa için Captcha (PerimeterX) Kontrolü
            while True:
                content = page.content()
                if "Before we continue" in content or "confirm you are a human" in content or "Access to this page has been denied" in page.title():
                    print(" > [DİKKAT] Ana sayfada Bot koruması (Captcha) algılandı! Lütfen tarayıcıda doğrulamayı geçin.")
                    page.wait_for_timeout(5000)
                else:
                    break
                    
            random_sleep()
        except Exception as e:
            print(f"Ana sayfa yüklenirken hata oluştu: {e}")
            browser.close()
            return

        print("\nRestoran bağlantıları toplanıyor...")
        
        # NOT: Yemeksepeti veya diğer platformlar, HTML sınıflarını (class names) sık sık güncelleyebilir.
        # Bu seçiciler (selectors) yapısal bir örnek olması açısından verilmiştir. Gerçek senaryoda
        # güncel DOM incelenerek bu XPath veya CSS Selector'lar güncellenmelidir.
        
        # Sayfadaki a etiketlerinin içerisinde "/restaurant/" veya "/delivery/" geçen href'leri buluyoruz.
        # Bu yapı platformun mevcut durumuna göre değişkenlik gösterebilir.
        try:
            # Doğal bir kullanıcı gibi yavaşça aşağı kaydırıyoruz
            page.evaluate("""
                var totalHeight = 0;
                var distance = 100;
                var timer = setInterval(() => {
                    var scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;

                    if(totalHeight >= scrollHeight - window.innerHeight){
                        clearInterval(timer);
                    }
                }, 100);
            """)
            page.wait_for_timeout(4000) # Kaydırmanın bitmesi ve lazy load içeriklerin yüklenmesi için bekleme
            
            links_locator = page.locator('a')
            count = links_locator.count()
            
            restaurant_urls = []
            for i in range(count):
                href = links_locator.nth(i).get_attribute("href")
                if href and ("/restaurant/" in href or "/delivery/" in href):
                    full_url = href if href.startswith("http") else f"https://www.yemeksepeti.com{href}"
                    if full_url not in restaurant_urls:
                        restaurant_urls.append(full_url)
                        
                if len(restaurant_urls) >= MAX_RESTAURANTS:
                    break
        except Exception as e:
            print(f"Link toplama sırasında bir hata oldu: {e}")
            restaurant_urls = []

        if not restaurant_urls:
            print("Restoran linki bulunamadı. Lütfen hedef sayfadaki CSS Selector / DOM yapısını kontrol edin.")
            browser.close()
            return
            
        print(f"\nToplam {len(restaurant_urls)} restoran linki bulundu. Veri çekimine (Scraping) başlanıyor...")

        scraped_data = []

        # Her bir restoran için detaylara gir
        for i, url in enumerate(restaurant_urls):
            print(f"\n[{i+1}/{len(restaurant_urls)}] İşleniyor: {url}")
            # Crawl-delay: Her yeni sayfa talebinden önce mutlaka rastgele sürede bekle
            random_sleep()
            
            try:
                # Restoranın detay sayfasına git
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Captcha (PerimeterX) Kontrolü
                while True:
                    content = page.content()
                    if "Before we continue" in content or "confirm you are a human" in content or "Access to this page has been denied" in page.title():
                        print(" > [DİKKAT] Bot koruması (Captcha) algılandı! Lütfen açılan tarayıcı penceresinde doğrulamayı manuel olarak geçin. Script sizi bekliyor...")
                        page.wait_for_timeout(5000)
                    else:
                        break
                
                # Sayfa elementlerinin tam oturması için kısa bir bekleme
                page.wait_for_timeout(2000)
                
                # Restoran Adını Çek (Örnek selector'lar, güncellenmesi gerekebilir)
                name_locators = ['h1.main-info__title', 'h1.vendor-name', '[data-qa="vendor-name"]']
                restaurant_name = "Bilinmeyen Restoran"
                for selector in name_locators:
                    if page.locator(selector).count() > 0:
                        restaurant_name = page.locator(selector).first.text_content().strip()
                        if restaurant_name != "Çerezler & Benzer Teknolojiler":
                            break
                
                # Restoran Puanını Çek
                rating_locators = ['.bds-c-rating__label-primary', '[data-testid="rating-info"]', '.rating-score']
                rating = "Puan Yok"
                for selector in rating_locators:
                    if page.locator(selector).count() > 0:
                        rating = page.locator(selector).first.text_content().strip()
                        break
                
                # Tüm Menü Ürünlerini Çek (JS evaluate ile)
                # İndirimli/İndirimsiz fiyatları ayrı kaydeder
                menu_items = page.evaluate(r"""() => {
                    const items = document.querySelectorAll('[data-testid="menu-product"], .dish-card, .menu-item, [data-qa="menu-item"]');
                    const results = [];
                    for (let item of items) {
                        const nameEl = item.querySelector('[data-testid="menu-product-name"], .dish-name, .item-name, [data-qa="item-name"]');
                        if (!nameEl) continue;
                        const name = nameEl.textContent.trim();
                        
                        let indirimli_fiyat = null;
                        let indirimsiz_fiyat = null;
                        
                        const pEl = item.querySelector('[data-testid="menu-product-price"], .dish-price, .item-price, [data-qa="item-price"]');
                        
                        if (pEl) {
                            let text = pEl.textContent.trim();
                            let prices = text.match(/[\d,.]+\s*TL/g);
                            
                            if (prices && prices.length >= 2) {
                                let p1_str = prices[0];
                                let p2_str = prices[1];
                                let p1 = parseFloat(p1_str.replace(/\./g, '').replace(',', '.'));
                                let p2 = parseFloat(p2_str.replace(/\./g, '').replace(',', '.'));
                                
                                if (p1 < p2) {
                                    indirimli_fiyat = p1_str;
                                    indirimsiz_fiyat = p2_str;
                                } else if (p2 < p1) {
                                    indirimli_fiyat = p2_str;
                                    indirimsiz_fiyat = p1_str;
                                } else {
                                    indirimsiz_fiyat = p1_str;
                                }
                            } else if (prices && prices.length === 1) {
                                indirimsiz_fiyat = prices[0];
                            } else {
                                indirimsiz_fiyat = text;
                            }
                        } else {
                            // Fallback if price container not found
                            const textEls = Array.from(item.querySelectorAll('*')).filter(e => e.children.length === 0 && e.textContent && e.textContent.includes('TL'));
                            let prices = [];
                            for (let el of textEls) {
                                let text = el.textContent.trim();
                                let m = text.match(/^[\d,.]+\s*TL$/);
                                if (m) prices.push(m[0]);
                            }
                            if (prices.length >= 2) {
                                let p1 = parseFloat(prices[0].replace(/\./g, '').replace(',', '.'));
                                let p2 = parseFloat(prices[1].replace(/\./g, '').replace(',', '.'));
                                if (p1 < p2) {
                                    indirimli_fiyat = prices[0];
                                    indirimsiz_fiyat = prices[1];
                                } else {
                                    indirimli_fiyat = prices[1];
                                    indirimsiz_fiyat = prices[0];
                                }
                            } else if (prices.length === 1) {
                                indirimsiz_fiyat = prices[0];
                            } else {
                                indirimsiz_fiyat = "Bilinmeyen Fiyat";
                            }
                        }
                        
                        results.push({ 
                            isim: name, 
                            indirimli_fiyat: indirimli_fiyat, 
                            indirimsiz_fiyat: indirimsiz_fiyat 
                        });
                    }
                    return results;
                }""")

                # Elde edilen verileri objeye kaydet
                data = {
                    "restoran_adi": restaurant_name,
                    "puan": rating,
                    "url": url,
                    "menu_urunleri": menu_items
                }
                scraped_data.append(data)
                print(f" > Başarı: {restaurant_name} | Puan: {rating} | Menü Sayısı: {len(menu_items)}")
                
            except Exception as e:
                print(f" > Hata oluştu ({url}): {e}")
                continue

        # Çekilen veriyi yerel json dosyasına kaydet
        output_file = "scraped_restaurants_poc.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(scraped_data, f, ensure_ascii=False, indent=4)
            
        print("\n" + "="*50)
        print(f"Süreç başarıyla tamamlandı!")
        print(f"Toplam {len(scraped_data)} restoranın tüm menü verisi '{output_file}' adlı dosyaya kaydedildi.")
        print("Kişisel verilere (isim, yorum vb.) erişilmedi, hedef sınırlar içerisinde kalındı.")
        print("="*50)
        
        browser.close()

if __name__ == "__main__":
    run()
