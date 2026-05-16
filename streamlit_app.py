import json
from pathlib import Path

import pandas as pd
import streamlit as st

from scrapers.utils import normalize_text


DATA_PATH = Path("data/normalized/all_items.json")


st.set_page_config(
    page_title="NeYesem Demo",
    page_icon="🍽️",
    layout="wide",
)


@st.cache_data
def load_data():
    if not DATA_PATH.exists():
        return pd.DataFrame()

    with DATA_PATH.open("r", encoding="utf-8") as file:
        items = json.load(file)

    df = pd.DataFrame(items)

    required_columns = {
        "platform": None,
        "restaurant_name": None,
        "restaurant_rating": None,
        "item_name": None,
        "normalized_item_name": None,
        "price": None,
        "original_price": None,
        "discount_rate": None,
        "product_url": None,
        "city": None,
        "scraped_at": None,
    }

    for column, default_value in required_columns.items():
        if column not in df.columns:
            df[column] = default_value

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["original_price"] = pd.to_numeric(df["original_price"], errors="coerce")
    df["discount_rate"] = pd.to_numeric(df["discount_rate"], errors="coerce")

    df["search_text"] = (
        df["item_name"].fillna("").apply(normalize_text)
        + " "
        + df["restaurant_name"].fillna("").apply(normalize_text)
        + " "
        + df["platform"].fillna("").apply(normalize_text)
    )

    return df


def apply_filters(df, query, platforms, restaurants):
    filtered = df.copy()

    if query:
        q = normalize_text(query)
        filtered = filtered[filtered["search_text"].str.contains(q, na=False)]

    if platforms:
        filtered = filtered[filtered["platform"].isin(platforms)]

    if restaurants:
        filtered = filtered[filtered["restaurant_name"].isin(restaurants)]

    return filtered.sort_values("price", ascending=True)


def format_display_df(df):
    display = df.copy()

    display["Fiyat"] = display["price"].apply(
        lambda x: f"{x:.2f} TL" if pd.notna(x) else "-"
    )
    display["Eski Fiyat"] = display["original_price"].apply(
        lambda x: f"{x:.2f} TL" if pd.notna(x) else "-"
    )
    display["İndirim"] = display["discount_rate"].apply(
        lambda x: f"%{x:.1f}" if pd.notna(x) else "-"
    )

    display = display.rename(
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

    return display[
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


def show_best_price(df):
    if df.empty:
        return

    best = df.sort_values("price", ascending=True).iloc[0]

    st.success(
        f"En ucuz sonuç: **{best['platform']}** | "
        f"**{best['restaurant_name']}** | "
        f"**{best['item_name']}** → **{best['price']:.2f} TL**"
    )


def show_same_product_matches(df):
    if df.empty:
        st.info("Karşılaştırılacak sonuç yok.")
        return

    grouped = (
        df.groupby("normalized_item_name")
        .agg(
            urun=("item_name", "first"),
            platform_sayisi=("platform", "nunique"),
            en_dusuk_fiyat=("price", "min"),
            en_yuksek_fiyat=("price", "max"),
            sonuc_sayisi=("item_name", "count"),
        )
        .reset_index()
    )

    grouped = grouped[grouped["platform_sayisi"] >= 2]

    if grouped.empty:
        st.warning(
            "Bu aramada aynı ürün iki farklı platformda eşleşmedi. "
            "Bu normal olabilir; şu an veri farklı restoranlardan gelmiş olabilir."
        )
        return

    grouped["Fiyat Farkı"] = grouped["en_yuksek_fiyat"] - grouped["en_dusuk_fiyat"]

    grouped = grouped.rename(
        columns={
            "urun": "Ürün",
            "platform_sayisi": "Platform Sayısı",
            "en_dusuk_fiyat": "En Düşük Fiyat",
            "en_yuksek_fiyat": "En Yüksek Fiyat",
            "sonuc_sayisi": "Sonuç Sayısı",
        }
    )

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

st.title("🍽️ NeYesem Fiyat Karşılaştırma Demo")
st.write(
    "Yemeksepeti ve Trendyol verilerini ortak JSON formatında birleştirip "
    "ürün/restoran bazlı fiyat karşılaştırması yapan demo."
)

if df.empty:
    st.error(
        "Veri bulunamadı. Önce şu komutları çalıştır:\n\n"
        "`python .\\normalize_existing.py`\n\n"
        "`python .\\normalize_trendyol_sample.py`\n\n"
        "`python .\\combine_sources.py`"
    )
    st.stop()

with st.sidebar:
    st.header("Filtreler")

    query = st.text_input(
        "Ürün / restoran ara",
        value="",
        placeholder="Örn: waffle, su, berry, bubble",
    )

    all_platforms = sorted(df["platform"].dropna().unique().tolist())
    selected_platforms = st.multiselect(
        "Platform",
        options=all_platforms,
        default=all_platforms,
    )

    all_restaurants = sorted(df["restaurant_name"].dropna().unique().tolist())
    selected_restaurants = st.multiselect(
        "Restoran",
        options=all_restaurants,
        default=[],
    )

filtered_df = apply_filters(
    df=df,
    query=query,
    platforms=selected_platforms,
    restaurants=selected_restaurants,
)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Toplam Ürün", len(df))

with col2:
    st.metric("Gösterilen Sonuç", len(filtered_df))

with col3:
    st.metric("Platform", df["platform"].nunique())

with col4:
    st.metric("Restoran", df["restaurant_name"].nunique())

show_best_price(filtered_df)

tab1, tab2, tab3 = st.tabs(
    [
        "Fiyat Listesi",
        "Aynı Ürün Eşleşmeleri",
        "Platform Özeti",
    ]
)

with tab1:
    st.subheader("Fiyat Listesi")

    if filtered_df.empty:
        st.warning("Aramaya uygun sonuç bulunamadı.")
    else:
        display_df = format_display_df(filtered_df)

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn("Link"),
            },
        )

with tab2:
    st.subheader("Aynı Ürün Platform Karşılaştırması")
    show_same_product_matches(filtered_df)

with tab3:
    st.subheader("Platform Özeti")

    platform_summary = (
        filtered_df.groupby("platform")
        .agg(
            urun_sayisi=("item_name", "count"),
            ortalama_fiyat=("price", "mean"),
            minimum_fiyat=("price", "min"),
            maksimum_fiyat=("price", "max"),
        )
        .reset_index()
        .rename(
            columns={
                "platform": "Platform",
                "urun_sayisi": "Ürün Sayısı",
                "ortalama_fiyat": "Ortalama Fiyat",
                "minimum_fiyat": "Minimum Fiyat",
                "maksimum_fiyat": "Maksimum Fiyat",
            }
        )
    )

    st.dataframe(
        platform_summary,
        use_container_width=True,
        hide_index=True,
    )

    if not platform_summary.empty:
        st.bar_chart(
            platform_summary,
            x="Platform",
            y="Ortalama Fiyat",
        )

st.caption(
    "Not: Bu ekran akademik PoC demosudur. Veriler düşük hacimli olarak çekilip "
    "normalize edilmiştir. Fiyatlar partner platformlarda değişebilir."
)