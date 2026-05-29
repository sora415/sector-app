import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
import pytz

st.set_page_config(
    page_title="セクター別パフォーマンス",
    layout="wide",
    page_icon="📊",
)

US_SECTORS = {
    "テクノロジー":     "XLK",
    "金融":             "XLF",
    "ヘルスケア":       "XLV",
    "エネルギー":       "XLE",
    "素材":             "XLB",
    "一般消費財":       "XLY",
    "生活必需品":       "XLP",
    "通信サービス":     "XLC",
    "不動産":           "XLRE",
    "公益事業":         "XLU",
    "資本財":           "XLI",
}

JP_SECTORS = {
    "食品":             "1617.T",
    "エネルギー資源":   "1618.T",
    "建設・資材":       "1619.T",
    "素材・化学":       "1620.T",
    "医薬品":           "1621.T",
    "自動車・輸送機":   "1622.T",
    "鉄鋼・非鉄":       "1623.T",
    "機械":             "1624.T",
    "電機・精密":       "1625.T",
    "情報通信・サービス": "1626.T",
    "電力・ガス":       "1627.T",
    "運輸・物流":       "1628.T",
    "商社・卸売":       "1629.T",
    "小売":             "1630.T",
    "銀行":             "1631.T",
    "金融(除く銀行)":   "1632.T",
    "不動産":           "1633.T",
}


def get_market_status():
    jst = pytz.timezone("Asia/Tokyo")
    est = pytz.timezone("America/New_York")
    now_jst = datetime.now(jst)
    now_est = datetime.now(est)
    weekday = now_jst.weekday()  # 0=月曜 〜 4=金曜

    # 日本市場: 平日 9:00〜11:30 / 12:30〜15:30 JST
    jp_open = False
    if weekday < 5:
        t = (now_jst.hour, now_jst.minute)
        if (9, 0) <= t < (11, 30) or (12, 30) <= t < (15, 30):
            jp_open = True

    # 米国市場: 平日 9:30〜16:00 EST
    us_weekday = now_est.weekday()
    us_open = False
    if us_weekday < 5:
        t = (now_est.hour, now_est.minute)
        if (9, 30) <= t < (16, 0):
            us_open = True

    return now_jst, now_est, jp_open, us_open


@st.cache_data(ttl=300)
def fetch_performance(sectors: dict) -> pd.DataFrame:
    results = []
    for name, sym in sectors.items():
        try:
            hist = yf.Ticker(sym).history(period="5d", interval="1d", auto_adjust=True)
            hist = hist.dropna(subset=["Close"])
            if len(hist) >= 2:
                prev = float(hist["Close"].iloc[-2])
                curr = float(hist["Close"].iloc[-1])
                pct = (curr - prev) / prev * 100
                results.append({
                    "セクター": name,
                    "変化率": round(pct, 2),
                    "現在値": round(curr, 2),
                    "ティッカー": sym,
                })
        except Exception:
            pass

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("変化率", ascending=True)
        .reset_index(drop=True)
    )


def market_badge(is_open: bool) -> str:
    return "🟢 取引中" if is_open else "🔴 閉場中"


def render_sector_view(sectors: dict, market_name: str):
    with st.spinner(f"{market_name}のデータを取得中..."):
        df = fetch_performance(sectors)

    if df.empty:
        st.error("データを取得できませんでした。しばらくしてから再試行してください。")
        return

    up = df[df["変化率"] > 0]
    dn = df[df["変化率"] < 0]
    best = df.iloc[-1]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("上昇セクター数", f"{len(up)} 業種")
    c2.metric("下落セクター数", f"{len(dn)} 業種")
    c3.metric("平均変化率", f"{df['変化率'].mean():+.2f}%")
    c4.metric("トップ", best["セクター"], delta=f"{best['変化率']:+.2f}%")

    st.divider()

    df["text"] = df["変化率"].apply(lambda x: f"{x:+.2f}%")

    fig = px.bar(
        df,
        x="変化率",
        y="セクター",
        orientation="h",
        text="text",
        color="変化率",
        color_continuous_scale=[
            [0.0, "#ef5350"],
            [0.5, "#f5f5f5"],
            [1.0, "#26a69a"],
        ],
        color_continuous_midpoint=0,
        title=f"{market_name}セクター 前日比パフォーマンス",
    )
    fig.update_traces(textposition="outside", marker_line_width=0)
    fig.update_layout(
        height=max(420, len(df) * 44),
        coloraxis_showscale=False,
        xaxis_title="前日比 (%)",
        yaxis_title="",
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13),
        margin=dict(l=10, r=110, t=50, b=10),
    )
    fig.add_vline(x=0, line_width=1.5, line_color="rgba(120,120,120,0.6)")

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 詳細テーブルを表示"):
        tbl = df[["セクター", "変化率", "現在値", "ティッカー"]].copy()
        tbl["変化率"] = tbl["変化率"].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(tbl.sort_values("セクター"), hide_index=True, use_container_width=True)


# ── メイン ──────────────────────────────────────────────
st.title("📊 セクター別パフォーマンス")

now_jst, now_est, jp_open, us_open = get_market_status()

# 時刻・市場ステータス表示
col_jst, col_est, col_btn = st.columns([2, 2, 1])
with col_jst:
    st.info(f"🇯🇵 日本時間　{now_jst.strftime('%m/%d %H:%M')}　{market_badge(jp_open)}")
with col_est:
    st.info(f"🇺🇸 NY時間　{now_est.strftime('%m/%d %H:%M')}　{market_badge(us_open)}")
with col_btn:
    if st.button("🔄 更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

tab_us, tab_jp = st.tabs(["🇺🇸 米国 (S&P500セクターETF)", "🇯🇵 日本 (TOPIX-17 ETF)"])

with tab_us:
    render_sector_view(US_SECTORS, "米国")

with tab_jp:
    render_sector_view(JP_SECTORS, "日本")

st.divider()
st.caption("データ: Yahoo Finance ｜ 米国: SPDR セクターETF ｜ 日本: NEXT FUNDS TOPIX-17 ETF")

