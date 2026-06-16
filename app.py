import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(
    page_title="マーケット全景",
    layout="wide",
    page_icon="📡",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background: #0d1117; }
  [data-testid="stHeader"] { background: transparent; }
  section[data-testid="stSidebar"] { display: none; }
  .block-container { padding: 1.2rem 2rem 2rem; max-width: 1400px; }

  /* index strip cards */
  .idx-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 10px 14px;
    text-align: center;
    min-width: 0;
  }
  .idx-label { font-size: 11px; color: #8b949e; font-weight: 600; letter-spacing: .04em; }
  .idx-price { font-size: 17px; font-weight: 700; color: #e6edf3; margin: 2px 0 1px; }
  .idx-chg-up   { font-size: 13px; font-weight: 600; color: #3fb950; }
  .idx-chg-down { font-size: 13px; font-weight: 600; color: #f85149; }

  /* period toggle */
  div[data-baseweb="radio"] label { color: #8b949e !important; font-size: 13px; }
  div[data-baseweb="radio"] label[data-checked="true"] { color: #58a6ff !important; }

  /* metric cards */
  [data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 16px;
  }
  [data-testid="metric-container"] label { color: #8b949e !important; font-size: 12px; }
  [data-testid="metric-container"] [data-testid="stMetricValue"] { color: #e6edf3 !important; font-size: 22px; }

  h1 { color: #e6edf3 !important; font-size: 22px !important; font-weight: 700 !important; margin-bottom: 0 !important; }
  .stTabs [data-baseweb="tab-list"] { background: #161b22; border-radius: 8px; padding: 4px; gap: 2px; }
  .stTabs [data-baseweb="tab"] { color: #8b949e; border-radius: 6px; font-size: 14px; font-weight: 600; }
  .stTabs [aria-selected="true"] { background: #21262d !important; color: #58a6ff !important; }
  .stDivider { border-color: #30363d !important; }
  .stSpinner > div { border-top-color: #58a6ff !important; }
  footer { display: none; }
</style>
""", unsafe_allow_html=True)

# ─── Sector / Index definitions ───────────────────────────────────────────────
INDICES = [
    ("NASDAQ",    "^IXIC"),
    ("S&P 500",   "^GSPC"),
    ("Dow",       "^DJI"),
    ("VIX",       "^VIX"),
    ("日経225",   "^N225"),
    ("USD/JPY",   "JPY=X"),
    ("Gold",      "GC=F"),
    ("WTI",       "CL=F"),
]

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

GLOBAL_MARKETS = {
    "米国 S&P500":    "SPY",
    "日本":           "EWJ",
    "ドイツ":         "EWG",
    "英国":           "EWU",
    "フランス":       "EWQ",
    "中国":           "FXI",
    "インド":         "INDA",
    "韓国":           "EWY",
    "ブラジル":       "EWZ",
    "オーストラリア": "EWA",
    "新興国(全体)":   "EEM",
    "先進国(米除く)": "EFA",
}

COMMODITIES = {
    "原油(WTI)":          "USO",
    "原油(ブレント)":     "BNO",
    "天然ガス":           "UNG",
    "ガソリン":           "UGA",
    "エネルギーETF":      "XLE",
    "石油・ガス開発":     "XOP",
    "金(Gold)":           "GLD",
    "銀(Silver)":         "SLV",
    "銅":                 "CPER",
    "農産物(全般)":       "DBA",
    "小麦":               "WEAT",
    "大豆":               "SOYB",
    "トウモロコシ":       "CORN",
    "砂糖":               "SGG",
    "木材":               "WOOD",
}

THEMATIC = {
    "AI・ロボット":         "BOTZ",
    "AI革新(ARK)":          "ARKK",
    "半導体":               "SOXX",
    "クラウド":             "SKYY",
    "サイバーセキュリティ": "HACK",
    "EV・電動化":           "LIT",
    "クリーンエネルギー":   "ICLN",
    "宇宙・防衛":           "ITA",
    "バイオテック":         "XBI",
    "医療機器":             "IHI",
    "フィンテック":         "FINX",
    "ゲーミング・eスポーツ":"ESPO",
    "メタバース・VR":       "METV",
    "インフラ":             "PAVE",
    "小型株(Russell2000)":  "IWM",
}

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

PERIOD_OPTS = {"前日比": "1d", "5日間": "5d", "1ヶ月": "1mo"}

# ─── Data fetching ────────────────────────────────────────────────────────────

def fetch_multi(symbol: str) -> dict | None:
    """Returns pct_1d, pct_5d, pct_1mo and price in one yfinance call."""
    try:
        hist = yf.Ticker(symbol).history(period="1mo", interval="1d", auto_adjust=True)
        hist = hist.dropna(subset=["Close"])
        closes = hist["Close"]
        if len(closes) < 2:
            return None
        price = float(closes.iloc[-1])
        pct_1d = round((price - float(closes.iloc[-2])) / float(closes.iloc[-2]) * 100, 2)
        pct_5d_base = float(closes.iloc[-6]) if len(closes) >= 6 else float(closes.iloc[0])
        pct_5d = round((price - pct_5d_base) / pct_5d_base * 100, 2)
        pct_1mo = round((price - float(closes.iloc[0])) / float(closes.iloc[0]) * 100, 2)
        return {"price": round(price, 2), "pct_1d": pct_1d, "pct_5d": pct_5d, "pct_1mo": pct_1mo}
    except Exception:
        return None


@st.cache_data(ttl=300)
def fetch_index_strip() -> dict:
    results = {}
    with ThreadPoolExecutor(max_workers=len(INDICES)) as ex:
        futs = {ex.submit(fetch_multi, sym): (label, sym) for label, sym in INDICES}
        for f in as_completed(futs):
            label, sym = futs[f]
            d = f.result()
            if d:
                results[label] = d
    return results


@st.cache_data(ttl=300)
def fetch_sector_data(sectors: dict) -> pd.DataFrame:
    items = list(sectors.items())
    rows = []
    with ThreadPoolExecutor(max_workers=len(items)) as ex:
        futs = {ex.submit(fetch_multi, sym): (name, sym) for name, sym in items}
        for f in as_completed(futs):
            name, sym = futs[f]
            d = f.result()
            if d:
                rows.append({"セクター": name, "ティッカー": sym, **d})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("pct_1d", ascending=True).reset_index(drop=True)


@st.cache_data(ttl=300)
def fetch_semicon_data() -> dict:
    all_tickers = list({t for _, _, tickers in SEMICON_SUBSECTORS for t in tickers})
    ticker_data: dict = {}
    with ThreadPoolExecutor(max_workers=min(len(all_tickers), 40)) as ex:
        futs = {ex.submit(fetch_multi, t): t for t in all_tickers}
        for f in as_completed(futs):
            t = futs[f]
            d = f.result()
            if d:
                ticker_data[t] = d
    return ticker_data


def build_semicon_df(ticker_data: dict, period_key: str) -> pd.DataFrame:
    pct_col = {"前日比": "pct_1d", "5日間": "pct_5d", "1ヶ月": "pct_1mo"}[period_key]
    rows = []
    for group, subsector, tickers in SEMICON_SUBSECTORS:
        perfs = [ticker_data[t][pct_col] for t in tickers if t in ticker_data]
        if perfs:
            avg = round(sum(perfs) / len(perfs), 2)
            rows.append({"group": group, "subsector": subsector, "pct": avg,
                         "size": max(abs(avg), 0.15)})
    return pd.DataFrame(rows)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_market_status():
    jst = pytz.timezone("Asia/Tokyo")
    est = pytz.timezone("America/New_York")
    now_jst = datetime.now(jst)
    now_est = datetime.now(est)
    def _open(now, ranges):
        t = (now.hour, now.minute)
        return now.weekday() < 5 and any(lo <= t < hi for lo, hi in ranges)
    jp_open = _open(now_jst, [((9, 0), (11, 30)), ((12, 30), (15, 30))])
    us_open = _open(now_est, [((9, 30), (16, 0))])
    return now_jst, now_est, jp_open, us_open


def chg_class(v): return "idx-chg-up" if v >= 0 else "idx-chg-down"
def chg_sign(v):  return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"

BAR_COLORS = [[0.0, "#6b0000"], [0.35, "#ef5350"],
              [0.5, "#37474f"],
              [0.65, "#26a69a"], [1.0, "#00bfa5"]]

TREE_COLORS = [[0.00, "#6b0000"], [0.30, "#2d0a0a"], [0.45, "#141f14"],
               [0.50, "#1a2a1a"], [0.60, "#1e4a1e"], [0.75, "#2d7a2d"],
               [0.90, "#3aaa3a"], [1.00, "#00d400"]]

DARK_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#c9d1d9", size=13),
    margin=dict(l=10, r=110, t=50, b=10),
)

# ─── UI Sections ──────────────────────────────────────────────────────────────

def render_index_strip(data: dict):
    cols = st.columns(len(INDICES))
    for col, (label, _) in zip(cols, INDICES):
        d = data.get(label)
        if not d:
            col.markdown(f'<div class="idx-card"><div class="idx-label">{label}</div><div class="idx-price">—</div></div>', unsafe_allow_html=True)
            continue
        cls = chg_class(d["pct_1d"])
        col.markdown(f"""
<div class="idx-card">
  <div class="idx-label">{label}</div>
  <div class="idx-price">{d['price']:,.2f}</div>
  <div class="{cls}">{chg_sign(d['pct_1d'])}</div>
</div>""", unsafe_allow_html=True)


def render_dashboard(us_df: pd.DataFrame, jp_df: pd.DataFrame, period_key: str):
    pct_col = {"前日比": "pct_1d", "5日間": "pct_5d", "1ヶ月": "pct_1mo"}[period_key]
    period_label = period_key

    st.markdown("#### 📊 米国 vs 日本 セクター比較")
    left, right = st.columns(2)

    for col, df, title in [(left, us_df, "🇺🇸 米国"), (right, jp_df, "🇯🇵 日本")]:
        if df.empty:
            col.info("データなし")
            continue
        sorted_df = df.sort_values(pct_col, ascending=True)
        sorted_df["text"] = sorted_df[pct_col].apply(lambda x: f"{x:+.2f}%")
        fig = px.bar(sorted_df, x=pct_col, y="セクター", orientation="h", text="text",
                     color=pct_col, color_continuous_scale=BAR_COLORS,
                     color_continuous_midpoint=0, title=f"{title} — {period_label}")
        fig.update_traces(textposition="outside", marker_line_width=0)
        fig.update_layout(height=max(380, len(df) * 38),
                          coloraxis_showscale=False,
                          xaxis_title="", yaxis_title="", showlegend=False,
                          **DARK_LAYOUT)
        fig.add_vline(x=0, line_width=1, line_color="rgba(140,140,140,0.4)")
        col.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 🏆 トップ5 / ワースト5")
    l2, r2 = st.columns(2)
    combined = pd.concat([
        us_df.assign(市場="🇺🇸 米国"),
        jp_df.assign(市場="🇯🇵 日本"),
    ]) if not us_df.empty and not jp_df.empty else pd.DataFrame()

    if not combined.empty:
        combined_sorted = combined.sort_values(pct_col, ascending=False).reset_index(drop=True)
        top5  = combined_sorted.head(5)[["市場", "セクター", pct_col]]
        bot5  = combined_sorted.tail(5)[["市場", "セクター", pct_col]].sort_values(pct_col)

        def fmt(df):
            d = df.copy()
            d[pct_col] = d[pct_col].apply(lambda x: f"{x:+.2f}%")
            d.columns = ["市場", "セクター", f"変化率({period_label})"]
            return d

        l2.markdown("**上昇 トップ 5**")
        l2.dataframe(fmt(top5), hide_index=True, use_container_width=True)
        r2.markdown("**下落 ワースト 5**")
        r2.dataframe(fmt(bot5), hide_index=True, use_container_width=True)


def render_sector_tab(sectors: dict, market_name: str, period_key: str):
    pct_col = {"前日比": "pct_1d", "5日間": "pct_5d", "1ヶ月": "pct_1mo"}[period_key]
    df = fetch_sector_data(sectors)
    if df.empty:
        st.error("データを取得できませんでした。")
        return
    sorted_df = df.sort_values(pct_col, ascending=True)
    up = sorted_df[sorted_df[pct_col] > 0]
    dn = sorted_df[sorted_df[pct_col] < 0]
    best = sorted_df.iloc[-1]
    worst = sorted_df.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("上昇セクター", f"{len(up)} 業種")
    c2.metric("下落セクター", f"{len(dn)} 業種")
    c3.metric("平均変化率", f"{sorted_df[pct_col].mean():+.2f}%")
    c4.metric("トップ", best["セクター"], delta=f"{best[pct_col]:+.2f}%")
    st.markdown("")

    sorted_df["text"] = sorted_df[pct_col].apply(lambda x: f"{x:+.2f}%")
    fig = px.bar(sorted_df, x=pct_col, y="セクター", orientation="h", text="text",
                 color=pct_col, color_continuous_scale=BAR_COLORS,
                 color_continuous_midpoint=0,
                 title=f"{market_name} セクター — {period_key}")
    fig.update_traces(textposition="outside", marker_line_width=0)
    fig.update_layout(height=max(440, len(df) * 44),
                      coloraxis_showscale=False,
                      xaxis_title=f"{period_key} (%)", yaxis_title="", showlegend=False,
                      **DARK_LAYOUT)
    fig.add_vline(x=0, line_width=1.5, line_color="rgba(120,120,120,0.5)")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 詳細テーブルを表示"):
        tbl = sorted_df[["セクター", pct_col, "price", "ティッカー"]].copy()
        tbl.columns = ["セクター", f"変化率({period_key})", "現在値", "ティッカー"]
        tbl[f"変化率({period_key})"] = tbl[f"変化率({period_key})"].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(tbl.sort_values("セクター"), hide_index=True, use_container_width=True)


def render_semicon_tab(period_key: str):
    ticker_data = fetch_semicon_data()
    df = build_semicon_df(ticker_data, period_key)
    if df.empty:
        st.error("データを取得できませんでした。")
        return
    up = df[df["pct"] > 0]
    dn = df[df["pct"] < 0]
    c1, c2, c3 = st.columns(3)
    c1.metric("上昇サブセクター", f"{len(up)} 分野")
    c2.metric("下落サブセクター", f"{len(dn)} 分野")
    c3.metric("平均変化率", f"{df['pct'].mean():+.2f}%")

    fig = px.treemap(df, path=["group", "subsector"], values="size", color="pct",
                     color_continuous_scale=TREE_COLORS,
                     color_continuous_midpoint=0, custom_data=["pct"])
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%",
        textfont_size=12,
        marker_line_width=2,
        marker_line_color="rgba(0,0,0,0.6)",
        root_color="rgba(20,20,20,1)",
    )
    fig.update_layout(
        height=740,
        paper_bgcolor="rgba(14,14,14,1)",
        margin=dict(t=10, l=10, r=10, b=10),
        coloraxis_showscale=False,
        font=dict(color="#ffffff"),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 詳細テーブルを表示"):
        tbl = (df[["group", "subsector", "pct"]]
               .rename(columns={"group": "グループ", "subsector": "サブセクター", "pct": f"変化率({period_key})"})
               .sort_values(f"変化率({period_key})", ascending=False).reset_index(drop=True))
        tbl[f"変化率({period_key})"] = tbl[f"変化率({period_key})"].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(tbl, hide_index=True, use_container_width=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

now_jst, now_est, jp_open, us_open = get_market_status()

# Header row
h_left, h_right = st.columns([5, 1])
with h_left:
    jp_dot = "🟢" if jp_open else "🔴"
    us_dot = "🟢" if us_open else "🔴"
    st.markdown(
        f"<h1>📡 マーケット全景</h1>"
        f"<span style='color:#8b949e;font-size:13px'>"
        f"🇯🇵 {now_jst.strftime('%m/%d %H:%M')} {jp_dot}&nbsp;&nbsp;"
        f"🇺🇸 {now_est.strftime('%m/%d %H:%M')} {us_dot}</span>",
        unsafe_allow_html=True,
    )
with h_right:
    if st.button("🔄 更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# Index strip
with st.spinner("主要指数を取得中..."):
    idx_data = fetch_index_strip()
render_index_strip(idx_data)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# Period selector (shared across all tabs)
period_key = st.radio(
    "表示期間",
    list(PERIOD_OPTS.keys()),
    horizontal=True,
    label_visibility="collapsed",
)

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# Tabs
tab_dash, tab_us, tab_jp, tab_global, tab_theme, tab_commo, tab_semi = st.tabs([
    "🏠 概況ダッシュボード",
    "🇺🇸 米国セクター",
    "🇯🇵 日本セクター",
    "🌏 グローバル",
    "🚀 テーマ株",
    "🛢️ コモディティ",
    "🔬 半導体・AI ヒートマップ",
])

with tab_dash:
    with st.spinner("セクターデータ取得中..."):
        us_df = fetch_sector_data(US_SECTORS)
        jp_df = fetch_sector_data(JP_SECTORS)
    render_dashboard(us_df, jp_df, period_key)

with tab_us:
    with st.spinner("米国セクターデータ取得中..."):
        render_sector_tab(US_SECTORS, "米国", period_key)

with tab_jp:
    with st.spinner("日本セクターデータ取得中..."):
        render_sector_tab(JP_SECTORS, "日本", period_key)

with tab_global:
    with st.spinner("グローバル市場データ取得中..."):
        render_sector_tab(GLOBAL_MARKETS, "グローバル", period_key)

with tab_theme:
    with st.spinner("テーマ株データ取得中..."):
        render_sector_tab(THEMATIC, "テーマ株", period_key)

with tab_commo:
    with st.spinner("コモディティデータ取得中..."):
        render_sector_tab(COMMODITIES, "コモディティ", period_key)

with tab_semi:
    with st.spinner("半導体・AI詳細データ取得中..."):
        render_semicon_tab(period_key)

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
st.caption("データ: Yahoo Finance ｜ 米国: SPDR セクターETF ｜ 日本: NEXT FUNDS TOPIX-17 ETF ｜ 半導体: 代表銘柄の平均変化率 ｜ キャッシュ: 5分")
