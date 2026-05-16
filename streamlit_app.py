import json
from pathlib import Path

import pandas as pd
import streamlit as st

from scrapers.utils import normalize_text


DATA_PATH = Path("data/normalized/all_items.json")


st.set_page_config(
    page_title="NeYesem Fiyat Karşılaştırma",
    page_icon="🍽️",
    layout="wide",
)


def load_items():
    if not DATA_PATH.exists():
        return []

    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def to_dataframe(items):
    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(items)

    expected_columns = [
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

    for column in expected_columns:
        if column not in df.columns:
            df[column] = None

    return df[expected_columns]


def filter_items(df, query, selected_platforms, selected_restaurants):
    if df.empty:
        return df

    filtered = df.copy()

    if query:
        normalized_query = normalize_text(query)

        filtered = filtered[
            filtered["normalized_item_name"].fillna("").str.contains(
                normalized_query,
                case=False,
                na=False,
            )
            | filtered["restaurant_name"].fillna("").apply(normalize_text).str.contains(
                normalized_query,
                case=False,
                na=False,
            )
        ]

    if selected_platforms:
        filtered = filtered[filtered["platform"].isin(selected_platforms)]

    if selected_restaurants:
        filtered = filtered[filtered["restaurant_name"].isin(selected_restaurants)]

    filtered = filtered.sort_values(by="price", ascending=True)

    return filtered


def format_table(df):
    if df.empty:
        return df

    table = df.copy()

    table["price"] = table["price"].apply(
        lambda value: f"{value:.2f} TL" if pd.notna(value) else "-"
    )

    table["original_price"] = table["original_price"].apply(
        lambda value: f"{value:.2f} TL" if pd.notna(value) else "-"
    )

    table["discount_rate"] = table["discount_rate"].apply(
        lambda value: f"%{value:.1f}" if pd.notna(value) else "-"
    )

    table = table.rename(
        columns={
            "platform": "Platform",
            "restaurant_name": "Restoran",
            "restaurant_rating": "Puan",
            "item_name": "Ürün",
            "price": "Fiyat",
            "original_price": "Eski Fiyat",
            "discount_rate": "İndirim",
            "scraped_at": "Güncellenme Zamanı",
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
            "Güncellenme Zamanı",
            "Link",
        ]
    ]


def show_best_price_card(filtered_df):
    if filtered_df.empty:
        return

    best = filtered_df.iloc[0]

    st.success(
        f"En uygun seçenek: **{best['platform']}** üzerinde "
        f"**{best['restaurant_name']} - {best['item_name']}** "
        f"→ **{best['price']:.2f} TL**"
    )


items = load_items()
df = to_dataframe(items)

st.title("🍽️ NeYesem Fiyat Karşılaştırma Demo")
st.write(
    "Yemeksepeti ve Trendyol verilerini ortak formata çevirip "
    "ürün bazlı fiyat karşılaştırması yapan demo ekranı."
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
        "Yemek veya restoran ara",
        value="Berry Hibiscus",
        placeholder="Örn: burger, su, Big Bubble Tea",
    )

    platforms = sorted(df["platform"].dropna().unique().tolist())
    selected_platforms = st.multiselect(
        "Platform",
        options=platforms,
        default=platforms,
    )

    restaurants = sorted(df["restaurant_name"].dropna().unique().tolist())
    selected_restaurants = st.multiselect(
        "Restoran",
        options=restaurants,
        default=[],
    )

filtered_df = filter_items(
    df=df,
    query=query,
    selected_platforms=selected_platforms,
    selected_restaurants=selected_restaurants,
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Toplam ürün", len(df))

with col2:
    st.metric("Gösterilen sonuç", len(filtered_df))

with col3:
    st.metric("Platform sayısı", df["platform"].nunique())

show_best_price_card(filtered_df)

st.subheader("Karşılaştırma Sonuçları")

if filtered_df.empty:
    st.warning("Aramaya uygun sonuç bulunamadı.")
else:
    table = format_table(filtered_df)

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Platformlara Göre Ortalama Fiyat")

    average_price = (
        filtered_df.groupby("platform")["price"]
        .mean()
        .reset_index()
        .rename(columns={"platform": "Platform", "price": "Ortalama Fiyat"})
    )

    st.bar_chart(
        average_price,
        x="Platform",
        y="Ortalama Fiyat",
    )

st.caption(
    "Not: Trendyol verisi şu an demo/sample veri olarak eklenmiştir. "
    "Ama aynı normalizer formatı sayesinde canlı scraper çıktısı ile değiştirilebilir."
)