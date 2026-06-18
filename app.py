from __future__ import annotations
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

  div[data-baseweb="radio"] label { color: #8b949e !important; font-size: 13px; }
  div[data-baseweb="radio"] label[data-checked="true"] { color: #58a6ff !important; }

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

# ─── Index / Sector definitions ────────────────────────────────────────────────
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
    "テクノロジー": "XLK", "金融": "XLF", "ヘルスケア": "XLV", "エネルギー": "XLE",
    "素材": "XLB", "一般消費財": "XLY", "生活必需品": "XLP", "通信サービス": "XLC",
    "不動産": "XLRE", "公益事業": "XLU", "資本財": "XLI",
}

JP_SECTORS = {
    "食品": "1617.T", "エネルギー資源": "1618.T", "建設・資材": "1619.T",
    "素材・化学": "1620.T", "医薬品": "1621.T", "自動車・輸送機": "1622.T",
    "鉄鋼・非鉄": "1623.T", "機械": "1624.T", "電機・精密": "1625.T",
    "情報通信・サービス": "1626.T", "電力・ガス": "1627.T", "運輸・物流": "1628.T",
    "商社・卸売": "1629.T", "小売": "1630.T", "銀行": "1631.T",
    "金融(除く銀行)": "1632.T", "不動産": "1633.T",
}

GLOBAL_MARKETS = {
    "米国 S&P500": "SPY", "日本": "EWJ", "ドイツ": "EWG", "英国": "EWU",
    "フランス": "EWQ", "中国": "FXI", "インド": "INDA", "韓国": "EWY",
    "ブラジル": "EWZ", "オーストラリア": "EWA", "新興国(全体)": "EEM", "先進国(米除く)": "EFA",
}

COMMODITIES = {
    "原油(WTI)": "USO", "原油(ブレント)": "BNO", "天然ガス": "UNG", "ガソリン": "UGA",
    "エネルギーETF": "XLE", "石油・ガス開発": "XOP", "金(Gold)": "GLD", "銀(Silver)": "SLV",
    "銅": "CPER", "農産物(全般)": "DBA", "小麦": "WEAT", "大豆": "SOYB",
    "トウモロコシ": "CORN", "砂糖": "SGG", "木材": "WOOD",
}

THEMATIC = {
    "AI・ロボット": "BOTZ", "AI革新(ARK)": "ARKK", "半導体": "SOXX", "クラウド": "SKYY",
    "サイバーセキュリティ": "HACK", "EV・電動化": "LIT", "クリーンエネルギー": "ICLN",
    "宇宙・防衛": "ITA", "バイオテック": "XBI", "医療機器": "IHI", "フィンテック": "FINX",
    "ゲーミング・eスポーツ": "ESPO", "メタバース・VR": "METV", "インフラ": "PAVE",
    "小型株(Russell2000)": "IWM",
}

# ─── 個別株ヒートマップ (finviz/NASDAQ スタイル) ──────────────────────────────
# group(業界) -> [ticker, ...]   個別銘柄をタイルで表示
SEMICON_STOCKS = {
    "GPU / AIアクセラレータ": ["NVDA", "AMD", "AVGO", "INTC", "QCOM", "MRVL", "TSM"],
    "ファブレス・設計":       ["QCOM", "AVGO", "MRVL", "NXPI", "LSCC", "RMBS", "ALGM", "SITM"],
    "製造装置 (前工程)":      ["ASML", "AMAT", "LRCX", "KLAC", "ACLS", "ONTO", "AEIS", "KLIC", "UCTT", "ICHR"],
    "製造装置 (日本)":        ["8035.T", "6920.T", "6857.T", "7731.T", "6146.T", "6728.T", "6315.T"],
    "ファウンドリ / OSAT":    ["TSM", "GFS", "UMC", "ASX", "AMKR"],
    "メモリ / ストレージ":    ["MU", "WDC", "STX", "3436.T", "285A.T"],
    "アナログ / 電源IC":      ["TXN", "ADI", "MCHP", "ON", "MPWR", "STM", "NXPI", "DIOD", "POWI"],
    "パワー / SiC・GaN":      ["WOLF", "ON", "STM", "NVTS", "6963.T", "6504.T"],
    "通信・RF":               ["QCOM", "SWKS", "QRVO", "AVGO", "MTSI", "SLAB"],
    "光通信 / フォトニクス":  ["COHR", "LITE", "POET", "5802.T", "6965.T"],
    "EDA / 半導体IP":         ["SNPS", "CDNS", "ARM"],
    "半導体材料":             ["ENTG", "CMC", "4063.T", "4091.T", "3436.T", "5201.T"],
    "電子部品 (日本)":        ["6981.T", "6762.T", "6976.T", "6779.T", "6770.T", "6988.T"],
    "AIサーバー / DC電力":    ["SMCI", "DELL", "HPE", "VRT", "ANET", "PSTG"],
}

# NASDAQ-100 主要銘柄を業界別に（finvizスタイル）
NASDAQ_STOCKS = {
    "テクノロジー(半導体)":   ["NVDA", "AVGO", "AMD", "QCOM", "INTC", "TXN", "MU", "ADI", "MRVL", "NXPI", "MCHP", "ASML", "AMAT", "LRCX", "KLAC"],
    "テクノロジー(SW/HW)":    ["MSFT", "AAPL", "ADBE", "CRM", "ORCL", "CSCO", "INTU", "NOW", "PANW", "CRWD", "FTNT", "ADSK", "WDAY", "TEAM", "DDOG", "SNPS", "CDNS"],
    "通信サービス":           ["GOOGL", "GOOG", "META", "NFLX", "CMCSA", "TMUS", "CHTR", "WBD", "EA", "TTWO"],
    "一般消費財":             ["AMZN", "TSLA", "MELI", "BKNG", "SBUX", "MAR", "ABNB", "ORLY", "ROST", "LULU", "PDD", "DASH"],
    "ヘルスケア":             ["AMGN", "GILD", "VRTX", "REGN", "ISRG", "MRNA", "DXCM", "IDXX", "BIIB", "ILMN"],
    "生活必需品":             ["COST", "PEP", "MDLZ", "KDP", "MNST", "KHC", "CTAS"],
    "資本財 / その他":        ["HON", "AMAT", "PCAR", "CSX", "FAST", "ODFL", "PAYX", "CTAS", "ADP"],
    "金融 / フィンテック":    ["PYPL", "FISV", "INTU", "CME"],
}

PERIOD_OPTS = {"前日比": "1d", "5日間": "5d", "1ヶ月": "1mo"}

# 銘柄表示名（日本株や見にくいティッカーに短い名前を付ける）
TICKER_NAMES = {
    "8035.T": "東京エレク", "6920.T": "レーザーテック", "6857.T": "アドバンテスト",
    "7731.T": "ニコン", "6146.T": "ディスコ", "6728.T": "アルバック",
    "6315.T": "TOWA", "3436.T": "SUMCO", "285A.T": "キオクシア",
    "6963.T": "ローム", "6504.T": "富士電機", "5802.T": "住友電工",
    "6965.T": "浜松ホト", "4063.T": "信越化学", "4091.T": "日本酸素",
    "5201.T": "AGC", "6981.T": "村田製作所", "6762.T": "TDK",
    "6976.T": "太陽誘電", "6779.T": "日本電波", "6770.T": "アルプスアル",
    "6988.T": "日東電工",
}


def disp_name(ticker: str) -> str:
    return TICKER_NAMES.get(ticker, ticker)


# ─── Data fetching ──────────────────────────────────────────────────────────────

def fetch_multi(symbol: str) -> dict | None:
    """1d/5d/1mo 変化率・価格・時価総額を1回の呼び出しで返す。"""
    try:
        tk = yf.Ticker(symbol)
        hist = tk.history(period="1mo", interval="1d", auto_adjust=True)
        hist = hist.dropna(subset=["Close"])
        closes = hist["Close"]
        if len(closes) < 2:
            return None
        price = float(closes.iloc[-1])
        pct_1d = round((price - float(closes.iloc[-2])) / float(closes.iloc[-2]) * 100, 2)
        base5 = float(closes.iloc[-6]) if len(closes) >= 6 else float(closes.iloc[0])
        pct_5d = round((price - base5) / base5 * 100, 2)
        pct_1mo = round((price - float(closes.iloc[0])) / float(closes.iloc[0]) * 100, 2)
        mcap = 0.0
        try:
            fi = tk.fast_info
            mcap = float(fi.get("marketCap") or fi.get("market_cap") or 0)
        except Exception:
            mcap = 0.0
        return {"price": round(price, 2), "pct_1d": pct_1d, "pct_5d": pct_5d,
                "pct_1mo": pct_1mo, "mcap": mcap}
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
def fetch_stocks_data(stocks_map: dict) -> dict:
    """個別株マップに含まれる全ティッカーを並列取得。"""
    all_tickers = list({t for tickers in stocks_map.values() for t in tickers})
    out: dict = {}
    with ThreadPoolExecutor(max_workers=min(len(all_tickers), 40)) as ex:
        futs = {ex.submit(fetch_multi, t): t for t in all_tickers}
        for f in as_completed(futs):
            t = futs[f]
            d = f.result()
            if d:
                out[t] = d
    return out


def build_heatmap_df(ticker_data: dict, stocks_map: dict, period_key: str) -> pd.DataFrame:
    pct_col = {"前日比": "pct_1d", "5日間": "pct_5d", "1ヶ月": "pct_1mo"}[period_key]
    rows, seen = [], set()
    for group, tickers in stocks_map.items():
        for t in tickers:
            if t not in ticker_data:
                continue
            d = ticker_data[t]
            key = (group, t)
            if key in seen:
                continue
            seen.add(key)
            mcap = d.get("mcap", 0) or 0
            # 日本株の時価総額は円建てなのでドル換算（タイル面積を米株と揃える）
            if t.endswith(".T") and mcap > 0:
                mcap = mcap / 150.0
            # 時価総額(十億ドル)をサイズに。取れない時は中位の固定値。
            size = (mcap / 1e9) if mcap > 0 else 30.0
            size = max(size, 3.0)
            rows.append({
                "group": group,
                "ticker": t,
                "label": disp_name(t),
                "pct": d[pct_col],
                "price": d["price"],
                "size": size,
            })
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

# finviz風: 赤(下落)→暗灰(中立)→緑(上昇)
HEAT_COLORS = [[0.00, "#8b0000"], [0.25, "#c0392b"], [0.42, "#7a3a3a"],
               [0.50, "#3a3a3a"], [0.58, "#2f6b2f"], [0.75, "#27a527"],
               [1.00, "#00c800"]]

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


def render_heatmap_tab(stocks_map: dict, title: str, period_key: str, height: int = 760):
    """finviz/NASDAQ スタイル: 個別銘柄を時価総額サイズのタイルで表示。"""
    ticker_data = fetch_stocks_data(stocks_map)
    df = build_heatmap_df(ticker_data, stocks_map, period_key)
    if df.empty:
        st.error("データを取得できませんでした。")
        return

    up = df[df["pct"] > 0]
    dn = df[df["pct"] < 0]
    best = df.loc[df["pct"].idxmax()]
    worst = df.loc[df["pct"].idxmin()]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("上昇銘柄", f"{len(up)} 社")
    c2.metric("下落銘柄", f"{len(dn)} 社")
    c3.metric("最高", best["label"], delta=f"{best['pct']:+.2f}%")
    c4.metric("最低", worst["label"], delta=f"{worst['pct']:+.2f}%")
    st.markdown("")

    cmax = max(3.0, df["pct"].abs().quantile(0.95))
    fig = px.treemap(
        df, path=[px.Constant(title), "group", "label"],
        values="size", color="pct",
        color_continuous_scale=HEAT_COLORS,
        range_color=[-cmax, cmax],
        color_continuous_midpoint=0,
        custom_data=["pct", "price"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%",
        textfont=dict(size=15, color="#ffffff"),
        textposition="middle center",
        marker_line_width=1.5,
        marker_line_color="rgba(13,17,23,1)",
        root_color="rgba(13,17,23,1)",
        hovertemplate="<b>%{label}</b><br>変化率: %{customdata[0]:+.2f}%<br>株価: %{customdata[1]:,.2f}<extra></extra>",
        tiling=dict(pad=2),
    )
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(13,17,23,1)",
        margin=dict(t=10, l=6, r=6, b=6),
        coloraxis_showscale=False,
        font=dict(color="#ffffff"),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 詳細テーブルを表示"):
        tbl = (df[["group", "label", "ticker", "pct", "price"]]
               .rename(columns={"group": "グループ", "label": "銘柄", "ticker": "ティッカー",
                                "pct": f"変化率({period_key})", "price": "現在値"})
               .sort_values(f"変化率({period_key})", ascending=False).reset_index(drop=True))
        tbl[f"変化率({period_key})"] = tbl[f"変化率({period_key})"].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(tbl, hide_index=True, use_container_width=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

now_jst, now_est, jp_open, us_open = get_market_status()

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

with st.spinner("主要指数を取得中..."):
    idx_data = fetch_index_strip()
render_index_strip(idx_data)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

period_key = st.radio(
    "表示期間",
    list(PERIOD_OPTS.keys()),
    horizontal=True,
    label_visibility="collapsed",
)

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

tab_dash, tab_us, tab_jp, tab_global, tab_theme, tab_commo, tab_semi, tab_ndx = st.tabs([
    "🏠 概況ダッシュボード",
    "🇺🇸 米国セクター",
    "🇯🇵 日本セクター",
    "🌏 グローバル",
    "🚀 テーマ株",
    "🛢️ コモディティ",
    "🔬 半導体ヒートマップ",
    "💹 NASDAQヒートマップ",
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
    with st.spinner("半導体・AI個別株データ取得中..."):
        render_heatmap_tab(SEMICON_STOCKS, "半導体・AI", period_key, height=780)

with tab_ndx:
    with st.spinner("NASDAQ個別株データ取得中..."):
        render_heatmap_tab(NASDAQ_STOCKS, "NASDAQ", period_key, height=820)

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
st.caption("データ: Yahoo Finance ｜ ヒートマップ: 個別銘柄をタイル表示・面積=時価総額・色=変化率 ｜ キャッシュ: 5分")
