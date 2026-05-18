import json
import html
from pathlib import Path

import pandas as pd
import streamlit as st

from scrapers.utils import normalize_text


DATA_PATH = Path("data/normalized/all_items.json")


st.set_page_config(
    page_title="NeYesem | Akıllı Fiyat Karşılaştırma",
    page_icon="🍽️",
    layout="wide",
)


st.markdown(
    """
    <style>
        .main-title {
            font-size: 42px;
            font-weight: 800;
            margin-bottom: 0px;
        }
        .sub-title {
            font-size: 18px;
            color: #666;
            margin-top: 4px;
            margin-bottom: 24px;
        }
        .hero-card {
            padding: 22px;
            border-radius: 18px;
            background: linear-gradient(135deg, #fff4ec 0%, #f8fbff 100%);
            border: 1px solid #f0e3d8;
            margin-bottom: 20px;
        }
        .best-card {
            padding: 20px;
            border-radius: 16px;
            background-color: #ecfff7;
            border: 1px solid #b7efd7;
            margin-top: 12px;
            margin-bottom: 20px;
        }
        .warning-card {
            padding: 16px;
            border-radius: 14px;
            background-color: #fff8e8;
            border: 1px solid #ffe0a3;
            margin-top: 12px;
            margin-bottom: 16px;
        }
        .small-muted {
            color: #777;
            font-size: 14px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    if not DATA_PATH.exists():
        return pd.DataFrame()

    with DATA_PATH.open("r", encoding="utf-8") as file:
        items = json.load(file)

    df = pd.DataFrame(items)

    required_columns = [
        "platform",
        "restaurant_name",
        "restaurant_rating",
        "item_name",
        "normalized_item_name",
        "price",
        "original_price",
        "discount_rate",
        "product_url",
        "city",
        "scraped_at",
    ]

    for column in required_columns:
        if column not in df.columns:
            df[column] = None

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["original_price"] = pd.to_numeric(df["original_price"], errors="coerce")
    df["discount_rate"] = pd.to_numeric(df["discount_rate"], errors="coerce")

    df["normalized_item_name"] = df["normalized_item_name"].fillna(
        df["item_name"].fillna("").apply(normalize_text)
    )

    # Scrape sırasında sayfadan ürün yerine yanlışlıkla yakalanan UI metinlerini temizle
    bad_item_patterns = [
        "şu anda temsili restoranları görüntülemekte",
        "su anda temsili restoranlari goruntulemekte",
        "aradığınız sayfa bulunamadı",
        "anasayfaya dön",
        "cookie",
        "çerez",
    ]

    def is_bad_item_name(value):
        raw = str(value or "").lower()
        normalized = normalize_text(raw)
        return any(pattern in raw or pattern in normalized for pattern in bad_item_patterns)

    df = df[~df["item_name"].apply(is_bad_item_name)].copy()

    df["search_text"] = (
        df["item_name"].fillna("").apply(normalize_text)
        + " "
        + df["restaurant_name"].fillna("").apply(normalize_text)
        + " "
        + df["platform"].fillna("").apply(normalize_text)
        + " "
        + df["city"].fillna("").apply(normalize_text)
    )

    return df


def money(value):
    if pd.isna(value):
        return "-"
    return f"{value:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def percent(value):
    if pd.isna(value):
        return "-"
    return f"%{value:.1f}"


def safe(value):
    if value is None or pd.isna(value):
        return "-"
    return html.escape(str(value))


def tokenize(value):
    normalized = normalize_text(value)
    return [token for token in normalized.split() if token]


def raw_tokenize(value):
    import re
    raw = str(value or "").lower()
    return re.findall(r"[a-zçğıöşü0-9]+", raw)


def smart_match(value, query):
    """
    Kısa aramalarda tam kelime eşleşmesi yapar.
    'su' aramasında 'şu', 'sultan', 'suadiye', 'sucuk' gelmez.
    Ayrıca demo için 'su böreği' gibi yemekleri içme suyu aramasından ayırır.
    """
    raw_query = str(query or "").lower().strip()
    raw_value = str(value or "").lower().strip()

    q = normalize_text(query)
    text = normalize_text(value)

    if not q:
        return True

    query_tokens = tokenize(q)
    text_tokens = tokenize(text)
    raw_query_tokens = raw_tokenize(raw_query)
    raw_value_tokens = raw_tokenize(raw_value)

    if not query_tokens:
        return True

    # Özel demo durumu: "su" araması içme suyu ürünlerini getirsin
    if raw_query == "su":
        if "su" not in raw_value_tokens:
            return False

        excluded_food_words = [
            "böreği",
            "börek",
            "boregi",
            "borek",
            "sucuk",
            "sulu",
        ]

        if any(word in raw_value or word in text for word in excluded_food_words):
            return False

        return True

    # Tek ve kısa kelimelerde önce ham token eşleşmesi kullan.
    # Böylece 'su' ile 'şu' eşleşmez.
    if len(raw_query_tokens) == 1 and len(raw_query_tokens[0]) <= 3:
        return raw_query_tokens[0] in raw_value_tokens

    # Çok kelimeli aramada tüm tokenlar geçsin
    if len(query_tokens) > 1:
        return all(token in text_tokens for token in query_tokens)

    # Uzun tek kelimelerde contains serbest
    return q in text


def filter_data(df, query, platforms, restaurants, sort_mode, search_scope):
    filtered = df.copy()

    if query:
        if search_scope == "Sadece ürün adı":
            filtered = filtered[
                filtered["item_name"].fillna("").apply(lambda value: smart_match(value, query))
            ]
        elif search_scope == "Sadece restoran adı":
            filtered = filtered[
                filtered["restaurant_name"].fillna("").apply(lambda value: smart_match(value, query))
            ]
        else:
            filtered = filtered[
                filtered["item_name"].fillna("").apply(lambda value: smart_match(value, query))
                | filtered["restaurant_name"].fillna("").apply(lambda value: smart_match(value, query))
                | filtered["platform"].fillna("").apply(lambda value: smart_match(value, query))
                | filtered["city"].fillna("").apply(lambda value: smart_match(value, query))
            ]

    if platforms:
        filtered = filtered[filtered["platform"].isin(platforms)]

    if restaurants:
        filtered = filtered[filtered["restaurant_name"].isin(restaurants)]

    if sort_mode == "En düşük fiyat":
        filtered = filtered.sort_values("price", ascending=True)
    elif sort_mode == "En yüksek indirim":
        filtered = filtered.sort_values("discount_rate", ascending=False)
    elif sort_mode == "Platform":
        filtered = filtered.sort_values(["platform", "price"], ascending=[True, True])
    else:
        filtered = filtered.sort_values("restaurant_name", ascending=True)

    return filtered


def build_display_table(df):
    table = df.copy()

    table["Fiyat"] = table["price"].apply(money)
    table["Eski Fiyat"] = table["original_price"].apply(money)
    table["İndirim"] = table["discount_rate"].apply(percent)

    table = table.rename(
        columns={
            "platform": "Platform",
            "restaurant_name": "Restoran",
            "restaurant_rating": "Puan",
            "item_name": "Ürün",
            "city": "Şehir",
            "scraped_at": "Güncellenme",
            "product_url": "Link",
        }
    )

    return table[
        [
            "Platform",
            "Restoran",
            "Puan",
            "Ürün",
            "Fiyat",
            "Eski Fiyat",
            "İndirim",
            "Şehir",
            "Güncellenme",
            "Link",
        ]
    ]


def show_best_option(df):
    valid = df.dropna(subset=["price"])

    if valid.empty:
        st.markdown(
            """
            <div class="warning-card">
                Bu filtrelerle fiyat bilgisi olan ürün bulunamadı.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    best = valid.sort_values("price", ascending=True).iloc[0]

    platform = safe(best["platform"])
    restaurant = safe(best["restaurant_name"])
    item = safe(best["item_name"])
    price = money(best["price"])
    old_price = money(best["original_price"])
    discount = percent(best["discount_rate"])

    st.markdown(
        f"""
        <div class="best-card">
            <h3>✅ En uygun seçenek</h3>
            <p style="font-size:18px; margin-bottom:6px;">
                <b>{item}</b>
            </p>
            <p style="margin-bottom:4px;">
                Platform: <b>{platform}</b> &nbsp; | &nbsp;
                Restoran: <b>{restaurant}</b>
            </p>
            <p style="font-size:22px; margin-top:10px;">
                <b>{price}</b>
                <span class="small-muted"> Eski fiyat: {old_price} | İndirim: {discount}</span>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_platform_summary(df):
    if df.empty:
        st.warning("Özet çıkarılacak veri bulunamadı.")
        return

    summary = (
        df.groupby("platform")
        .agg(
            urun_sayisi=("item_name", "count"),
            restoran_sayisi=("restaurant_name", "nunique"),
            ortalama_fiyat=("price", "mean"),
            minimum_fiyat=("price", "min"),
            maksimum_fiyat=("price", "max"),
        )
        .reset_index()
        .rename(
            columns={
                "platform": "Platform",
                "urun_sayisi": "Ürün Sayısı",
                "restoran_sayisi": "Restoran Sayısı",
                "ortalama_fiyat": "Ortalama Fiyat",
                "minimum_fiyat": "Minimum Fiyat",
                "maksimum_fiyat": "Maksimum Fiyat",
            }
        )
    )

    for column in ["Ortalama Fiyat", "Minimum Fiyat", "Maksimum Fiyat"]:
        summary[column] = summary[column].apply(money)

    st.dataframe(summary, use_container_width=True, hide_index=True)

    chart_df = (
        df.groupby("platform")["price"]
        .mean()
        .reset_index()
        .rename(columns={"platform": "Platform", "price": "Ortalama Fiyat"})
    )

    if not chart_df.empty:
        st.bar_chart(chart_df, x="Platform", y="Ortalama Fiyat")


def show_match_summary(df):
    if df.empty:
        st.warning("Eşleşme yapılacak veri bulunamadı.")
        return

    grouped = (
        df.groupby("normalized_item_name")
        .agg(
            urun=("item_name", "first"),
            platform_sayisi=("platform", "nunique"),
            sonuc_sayisi=("item_name", "count"),
            en_dusuk_fiyat=("price", "min"),
            en_yuksek_fiyat=("price", "max"),
        )
        .reset_index()
    )

    grouped = grouped[grouped["platform_sayisi"] >= 2]

    if grouped.empty:
        st.markdown(
            """
            <div class="warning-card">
                Bu aramada aynı ürün iki farklı platformda birebir eşleşmedi.
                Bu normal olabilir; şu an platformlardan çekilen restoranlar farklı olabilir.
                Veri kapsamı genişledikçe bu sekmede gerçek ürün eşleşmeleri artacaktır.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    grouped["fiyat_farki"] = grouped["en_yuksek_fiyat"] - grouped["en_dusuk_fiyat"]

    grouped = grouped.rename(
        columns={
            "urun": "Ürün",
            "platform_sayisi": "Platform Sayısı",
            "sonuc_sayisi": "Sonuç Sayısı",
            "en_dusuk_fiyat": "En Düşük Fiyat",
            "en_yuksek_fiyat": "En Yüksek Fiyat",
            "fiyat_farki": "Fiyat Farkı",
        }
    )

    for column in ["En Düşük Fiyat", "En Yüksek Fiyat", "Fiyat Farkı"]:
        grouped[column] = grouped[column].apply(money)

    st.dataframe(
        grouped[
            [
                "Ürün",
                "Platform Sayısı",
                "Sonuç Sayısı",
                "En Düşük Fiyat",
                "En Yüksek Fiyat",
                "Fiyat Farkı",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


df = load_data()

st.markdown(
    """
    <div class="hero-card">
        <div class="main-title">🍽️ NeYesem</div>
        <div class="sub-title">
            Yemek platformlarındaki ürünleri tek yerde toplayan, fiyatları karşılaştıran
            ve kullanıcıya en uygun seçeneği gösteren akıllı karar destek demosu.
        </div>
        <b>Demo kapsamı:</b> Yemeksepeti + Trendyol verileri ortak formata dönüştürülür,
        tek listede birleştirilir ve kullanıcı aramasına göre karşılaştırılır.
    </div>
    """,
    unsafe_allow_html=True,
)

if df.empty:
    st.error(
        "Veri bulunamadı. Önce şu komutları çalıştır:\n\n"
        "`python .\\normalize_existing.py`\n\n"
        "`python .\\normalize_trendyol.py`\n\n"
        "`python .\\combine_sources.py`"
    )
    st.stop()

with st.sidebar:
    st.header("🔎 Demo Kontrol Paneli")

    scenario = st.selectbox(
        "Hazır demo senaryosu",
        [
            "Serbest arama",
            "Waffle ara",
            "Su ara",
            "Bubble Tea ara",
            "Tüm ürünleri göster",
        ],
    )

    default_query = ""

    if scenario == "Waffle ara":
        default_query = "waffle"
    elif scenario == "Su ara":
        default_query = "su"
    elif scenario == "Bubble Tea ara":
        default_query = "bubble"
    elif scenario == "Tüm ürünleri göster":
        default_query = ""

    query = st.text_input(
        "Ürün / restoran ara",
        value=default_query,
        placeholder="Örn: waffle, su, burger, bubble",
    )

    search_scope = st.radio(
        "Arama alanı",
        ["Sadece ürün adı", "Sadece restoran adı", "Tüm alanlar"],
        index=0,
    )

    all_platforms = sorted(df["platform"].dropna().unique().tolist())
    selected_platforms = st.multiselect(
        "Platform seç",
        options=all_platforms,
        default=all_platforms,
    )

    all_restaurants = sorted(df["restaurant_name"].dropna().unique().tolist())
    selected_restaurants = st.multiselect(
        "Restoran filtrele",
        options=all_restaurants,
        default=[],
    )

    sort_mode = st.radio(
        "Sıralama",
        ["En düşük fiyat", "En yüksek indirim", "Platform", "Restoran"],
    )

filtered_df = filter_data(
    df=df,
    query=query,
    platforms=selected_platforms,
    restaurants=selected_restaurants,
    sort_mode=sort_mode,
    search_scope=search_scope,
)

latest_update = df["scraped_at"].dropna().max() if "scraped_at" in df.columns else "-"

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric("Toplam ürün", len(df))

with kpi2:
    st.metric("Gösterilen sonuç", len(filtered_df))

with kpi3:
    st.metric("Platform sayısı", df["platform"].nunique())

with kpi4:
    st.metric("Restoran sayısı", df["restaurant_name"].nunique())

show_best_option(filtered_df)

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Karşılaştırma",
        "Aynı Ürün Eşleşmeleri",
        "Platform Özeti",
        "Veri Akışı",
    ]
)

with tab1:
    st.subheader("Fiyat Karşılaştırma Listesi")

    if filtered_df.empty:
        st.warning("Bu arama/filtre için sonuç bulunamadı.")
    else:
        st.dataframe(
            build_display_table(filtered_df),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn("Link"),
            },
        )

with tab2:
    st.subheader("Aynı Ürün Eşleşmeleri")
    st.write(
        "Aynı ürün adı birden fazla platformda bulunduğunda fiyat farkı burada gösterilir."
    )
    show_match_summary(filtered_df)

with tab3:
    st.subheader("Platform Bazlı Özet")
    show_platform_summary(filtered_df)

with tab4:
    st.subheader("Veri İşleme Akışı")
    st.markdown(
        """
        Bu demo aşağıdaki akışla çalışır:

        1. **Veri çekme:** Yemeksepeti ve Trendyol kaynaklarından ürün/restoran verisi alınır.
        2. **Normalize etme:** Platformlara özel ham veri ortak JSON formatına çevrilir.
        3. **Birleştirme:** Tüm platform ürünleri `all_items.json` içinde toplanır.
        4. **Karşılaştırma:** Kullanıcı aramasına göre fiyatlar yan yana listelenir.
        5. **Karar desteği:** En ucuz seçenek ve platform özeti kullanıcıya gösterilir.

        Bu yapı daha sonra Getir Yemek çıktısı da eklenerek üç platformlu hale getirilebilir.
        """
    )

st.caption(
    f"Son veri güncelleme zamanı: {latest_update} | "
    "Bu ekran akademik PoC demosudur. Fiyatlar partner platformlarda değişebilir."
)
