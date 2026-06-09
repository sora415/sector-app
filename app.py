import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    "食品":               "1617.T",
    "エネルギー資源":     "1618.T",
    "建設・資材":         "1619.T",
    "素材・化学":         "1620.T",
    "医薬品":             "1621.T",
    "自動車・輸送機":     "1622.T",
    "鉄鋼・非鉄":         "1623.T",
    "機械":               "1624.T",
    "電機・精密":         "1625.T",
    "情報通信・サービス": "1626.T",
    "電力・ガス":         "1627.T",
    "運輸・物流":         "1628.T",
    "商社・卸売":         "1629.T",
    "小売":               "1630.T",
    "銀行":               "1631.T",
    "金融(除く銀行)":     "1632.T",
    "不動産":             "1633.T",
}

# 半導体・AI詳細サブセクター (グループ, サブセクター名, [ティッカー...])
SEMICON_SUBSECTORS = [
    ("メモリ・ストレージ",    "NAND / エンタープライズSSD",           ["285A.T", "WDC", "MU"]),
    ("メモリ・ストレージ",    "DRAM / CXLメモリ",                     ["MU", "3436.T"]),
    ("メモリ・ストレージ",    "HBM",                                  ["MU", "NVDA"]),
    ("メモリ・ストレージ",    "AIストレージシステム",                  ["NTAP", "PSTG"]),

    ("電子部品",              "MLCC",                                 ["6981.T", "6762.T", "6976.T"]),
    ("電子部品",              "パワーインダクタ",                     ["6762.T", "6981.T", "6773.T"]),
    ("電子部品",              "EMIフィルタ / フェライトビーズ",       ["6762.T", "6981.T"]),
    ("電子部品",              "サーミスタ / 温度センサー",            ["6981.T", "6762.T"]),
    ("電子部品",              "水晶デバイス / 低ジッタクロック",      ["6779.T", "6728.T"]),

    ("電力・受配電",          "パワー半導体",                         ["6504.T", "6723.T", "6963.T", "6503.T"]),
    ("電力・受配電",          "電線 / バスバー / 配線材",             ["5802.T", "5803.T", "5801.T"]),

    ("高速通信・光通信",      "CPO / シリコンフォトニクス",           ["5802.T", "5803.T"]),
    ("高速通信・光通信",      "光学部材 / 光コネクタ / 光ファイバー", ["5802.T", "5803.T", "5801.T"]),
    ("高速通信・光通信",      "光トランシーバー",                     ["5802.T", "6965.T"]),
    ("高速通信・光通信",      "レーザー / フォトダイオード",          ["6965.T", "6976.T"]),

    ("半導体製造装置",        "エッチング / 成膜",                    ["8035.T", "6728.T", "6590.T"]),
    ("半導体製造装置",        "露光装置 / EUV",                       ["7731.T", "7751.T", "ASML"]),
    ("半導体製造装置",        "洗浄 / CMP",                           ["7735.T", "6590.T"]),
    ("半導体製造装置",        "計測 / 検査",                          ["6920.T", "6857.T", "7729.T"]),
    ("半導体製造装置",        "後工程 / パッケージ装置",              ["6146.T", "6856.T"]),

    ("先端パッケージ・基板",  "CoWoS / 2.5D / 3Dパッケージ",         ["4062.T", "6967.T"]),
    ("先端パッケージ・基板",  "ABF基板 / 基板材料",                   ["4062.T", "6967.T"]),
    ("先端パッケージ・基板",  "インターポーザー / RDL / TSV",         ["4062.T", "6967.T"]),
    ("先端パッケージ・基板",  "フォトレジスト / 露光材料",            ["4063.T", "4186.T"]),
    ("先端パッケージ・基板",  "シリコンウェハ",                       ["4063.T", "3436.T"]),
    ("先端パッケージ・基板",  "ガラス基板",                           ["5201.T", "5214.T"]),

    ("半導体材料・高純度材料","特殊ガス / 高純度薬液",                ["4091.T", "4109.T"]),
    ("半導体材料・高純度材料","フォトマスク / ブランクス",            ["7741.T", "5201.T"]),
    ("半導体材料・高純度材料","シリコン材料",                         ["4063.T", "3436.T"]),

    ("AI・データセンター",    "GPU / AIアクセラレータ",               ["NVDA", "AMD"]),
    ("AI・データセンター",    "エッジAI SoC",                         ["6723.T", "6963.T", "AMD"]),
    ("AI・データセンター",    "CPU / DPU / NIC",                      ["NVDA", "AMD", "INTC", "MRVL"]),
    ("AI・データセンター",    "AIサーバー基板 / 高多層PCB",           ["4062.T", "6967.T"]),
    ("AI・データセンター",    "高速ケーブル / ケーブルアセンブリ",    ["5803.T", "5802.T"]),
    ("AI・データセンター",    "クラウドAI / AIサービス",              ["MSFT", "GOOGL", "AMZN"]),
    ("AI・データセンター",    "ロボット / 産業AI",                    ["6954.T", "6273.T", "6506.T"]),
    ("AI・データセンター",    "車載AI / ADAS",                        ["6902.T", "6723.T"]),
    ("AI・データセンター",    "データセンター建設",                   ["1801.T", "1802.T"]),
    ("AI・データセンター",    "熱交換器 / 冷却 / 空調",               ["6361.T", "6367.T"]),
]


def get_market_status():
    jst = pytz.timezone("Asia/Tokyo")
    est = pytz.timezone("America/New_York")
    now_jst = datetime.now(jst)
    now_est = datetime.now(est)
    weekday = now_jst.weekday()

    jp_open = False
    if weekday < 5:
        t = (now_jst.hour, now_jst.minute)
        if (9, 0) <= t < (11, 30) or (12, 30) <= t < (15, 30):
            jp_open = True

    us_weekday = now_est.weekday()
    us_open = False
    if us_weekday < 5:
        t = (now_est.hour, now_est.minute)
        if (9, 30) <= t < (16, 0):
            us_open = True

    return now_jst, now_est, jp_open, us_open


def fetch_single(symbol: str):
    """1銘柄の前日比(%)と現在値を返す。失敗時はNone。"""
    try:
        hist = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=True)
        hist = hist.dropna(subset=["Close"])
        if len(hist) >= 2:
            prev = float(hist["Close"].iloc[-2])
            curr = float(hist["Close"].iloc[-1])
            return {
                "pct":   round((curr - prev) / prev * 100, 2),
                "price": round(curr, 2),
            }
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def fetch_performance(sectors: dict) -> pd.DataFrame:
    """セクターETFの前日比を並列取得する。"""
    items = list(sectors.items())
    results = []

    with ThreadPoolExecutor(max_workers=len(items)) as ex:
        futures = {ex.submit(fetch_single, sym): (name, sym) for name, sym in items}
        for f in as_completed(futures):
            name, sym = futures[f]
            data = f.result()
            if data:
                results.append({
                    "セクター":   name,
                    "変化率":     data["pct"],
                    "現在値":     data["price"],
                    "ティッカー": sym,
                })

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("変化率", ascending=True)
        .reset_index(drop=True)
    )


@st.cache_data(ttl=300)
def fetch_semicon_heatmap() -> pd.DataFrame:
    """半導体サブセクターの前日比を並列取得してサブセクター平均を返す。"""
    all_tickers = list({t for _, _, tickers in SEMICON_SUBSECTORS for t in tickers})

    ticker_pct: dict = {}
    with ThreadPoolExecutor(max_workers=min(len(all_tickers), 40)) as ex:
        futures = {ex.submit(fetch_single, t): t for t in all_tickers}
        for f in as_completed(futures):
            t = futures[f]
            data = f.result()
            if data:
                ticker_pct[t] = data["pct"]

    rows = []
    for group, subsector, tickers in SEMICON_SUBSECTORS:
        perfs = [ticker_pct[t] for t in tickers if t in ticker_pct]
        if perfs:
            avg = round(sum(perfs) / len(perfs), 2)
            rows.append({
                "group":     group,
                "subsector": subsector,
                "pct":       avg,
                "size":      max(abs(avg), 0.15),
            })

    return pd.DataFrame(rows)


def market_badge(is_open: bool) -> str:
    return "🟢 取引中" if is_open else "🔴 閉場中"


def render_sector_view(sectors: dict, market_name: str):
    with st.spinner(f"{market_name}のデータを取得中..."):
        df = fetch_performance(sectors)

    if df.empty:
        st.error("データを取得できませんでした。しばらくしてから再試行してください。")
        return

    up   = df[df["変化率"] > 0]
    dn   = df[df["変化率"] < 0]
    best = df.iloc[-1]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("上昇セクター数", f"{len(up)} 業種")
    c2.metric("下落セクター数", f"{len(dn)} 業種")
    c3.metric("平均変化率",     f"{df['変化率'].mean():+.2f}%")
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


def render_semicon_heatmap():
    with st.spinner("半導体・AI詳細データを取得中（全銘柄を並列取得）..."):
        df = fetch_semicon_heatmap()

    if df.empty:
        st.error("データを取得できませんでした。")
        return

    up = df[df["pct"] > 0]
    dn = df[df["pct"] < 0]
    c1, c2, c3 = st.columns(3)
    c1.metric("上昇サブセクター", f"{len(up)} 分野")
    c2.metric("下落サブセクター", f"{len(dn)} 分野")
    c3.metric("平均変化率",       f"{df['pct'].mean():+.2f}%")

    fig = px.treemap(
        df,
        path=["group", "subsector"],
        values="size",
        color="pct",
        color_continuous_scale=[
            [0.00, "#6b0000"],
            [0.30, "#2d0a0a"],
            [0.45, "#141f14"],
            [0.50, "#1a2a1a"],
            [0.60, "#1e4a1e"],
            [0.75, "#2d7a2d"],
            [0.90, "#3aaa3a"],
            [1.00, "#00d400"],
        ],
        color_continuous_midpoint=0,
        custom_data=["pct"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%",
        textfont_size=12,
        marker_line_width=2,
        marker_line_color="rgba(0,0,0,0.6)",
        root_color="rgba(20,20,20,1)",
    )
    fig.update_layout(
        height=720,
        paper_bgcolor="rgba(14,14,14,1)",
        margin=dict(t=10, l=10, r=10, b=10),
        coloraxis_showscale=False,
        font=dict(color="#ffffff"),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 詳細テーブルを表示"):
        tbl = (
            df[["group", "subsector", "pct"]]
            .rename(columns={"group": "グループ", "subsector": "サブセクター", "pct": "前日比(%)"})
            .sort_values("前日比(%)", ascending=False)
            .reset_index(drop=True)
        )
        tbl["前日比(%)"] = tbl["前日比(%)"].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(tbl, hide_index=True, use_container_width=True)


# ── メイン ──────────────────────────────────────────────
st.title("📊 セクター別パフォーマンス")

now_jst, now_est, jp_open, us_open = get_market_status()

col_jst, col_est, col_btn = st.columns([2, 2, 1])
with col_jst:
    st.info(f"🇯🇵 日本時間　{now_jst.strftime('%m/%d %H:%M')}　{market_badge(jp_open)}")
with col_est:
    st.info(f"🇺🇸 NY時間　{now_est.strftime('%m/%d %H:%M')}　{market_badge(us_open)}")
with col_btn:
    if st.button("🔄 更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

tab_us, tab_jp, tab_semi = st.tabs([
    "🇺🇸 米国 (S&P500セクターETF)",
    "🇯🇵 日本 (TOPIX-17 ETF)",
    "🔬 半導体・AI 詳細ヒートマップ",
])

with tab_us:
    render_sector_view(US_SECTORS, "米国")

with tab_jp:
    render_sector_view(JP_SECTORS, "日本")

with tab_semi:
    render_semicon_heatmap()

st.divider()
st.caption("データ: Yahoo Finance ｜ 米国: SPDR セクターETF ｜ 日本: NEXT FUNDS TOPIX-17 ETF ｜ 半導体: 代表銘柄の平均前日比")
