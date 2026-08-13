# -*- coding: utf-8 -*-
"""
لوحة متابعة محفظة السوق السعودي (تداول) — نسخة الجوال.
التشغيل محلياً:  streamlit run tasi_dashboard.py

ملاحظة فنية مهمة: أي HTML يُمرَّر إلى st.markdown يجب ألا يبدأ سطره بمسافات بادئة،
لأن Markdown يعتبر أي سطر بمسافتين فأكثر "كتلة كود" فيعرضه كنص خام بدل تنفيذه.
"""

from __future__ import annotations

import math
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

try:
    from tradingview_ta import TA_Handler, Interval
    TV_AVAILABLE = True
except Exception:
    TV_AVAILABLE = False


# ==========================================================
# إعدادات
# ==========================================================

st.set_page_config(
    page_title="محفظتي | تداول",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

TV_SCREENERS = ["ksa", "saudiarabia", "saudi arabia"]
TV_EXCHANGE = "TADAWUL"
CACHE_TTL = 900
PLOT_CONFIG = {"displayModeBar": False, "scrollZoom": False}

TADAWUL_MAP = {
    "1010": ("بنك الرياض", "البنوك"),
    "1020": ("بنك الجزيرة", "البنوك"),
    "1030": ("البنك السعودي للاستثمار", "البنوك"),
    "1050": ("البنك السعودي الفرنسي", "البنوك"),
    "1060": ("البنك السعودي الأول", "البنوك"),
    "1080": ("البنك العربي الوطني", "البنوك"),
    "1111": ("مجموعة تداول السعودية", "الخدمات المالية"),
    "1120": ("مصرف الراجحي", "البنوك"),
    "1150": ("مصرف الإنماء", "البنوك"),
    "1180": ("البنك الأهلي السعودي", "البنوك"),
    "1211": ("معادن", "المواد الأساسية"),
    "2010": ("سابك", "المواد الأساسية"),
    "2020": ("سابك للمغذيات الزراعية", "المواد الأساسية"),
    "2050": ("صافولا", "السلع الاستهلاكية"),
    "2222": ("أرامكو السعودية", "الطاقة"),
    "2280": ("المراعي", "السلع الاستهلاكية"),
    "2350": ("كيان السعودية", "المواد الأساسية"),
    "2380": ("بترو رابغ", "الطاقة"),
    "3030": ("أسمنت السعودية", "المواد الأساسية"),
    "4002": ("المواساة", "الرعاية الصحية"),
    "4013": ("د. سليمان الحبيب", "الرعاية الصحية"),
    "4030": ("البحري", "النقل"),
    "4190": ("جرير", "التجزئة"),
    "5110": ("السعودية للكهرباء", "المرافق العامة"),
    "6010": ("نادك", "السلع الاستهلاكية"),
    "7010": ("الاتصالات السعودية stc", "الاتصالات"),
    "7020": ("اتحاد اتصالات موبايلي", "الاتصالات"),
    "7030": ("زين السعودية", "الاتصالات"),
    "8210": ("بوبا العربية", "التأمين"),
}

DEFAULT_ROWS = [
    {"code": "2222", "buy": 27.5, "qty": 100.0},
    {"code": "1120", "buy": 78.0, "qty": 50.0},
]

SECTOR_COLORS = ["#0E4D64", "#C08A2E", "#1E8E5A", "#8E5A9E", "#C0562B",
                 "#3C7A9E", "#7A8899", "#B03A5B", "#5A8E3C", "#6E5A3C"]


# ==========================================================
# التنسيق — لا تُضِف مسافات بادئة داخل هذه الكتلة
# ==========================================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap');

:root { --ink:#0E1B2C; --sand:#F5F1E8; --brass:#C08A2E;
--up:#1E8E5A; --down:#C0392B; --muted:#7A8899; }

html, body, [class*="css"], .stApp { direction: rtl; }
.stApp { background: var(--sand); }
#MainMenu, footer { visibility: hidden; }

h1,h2,h3,h4,h5,h6,p,div,span,label,li,td,th {
font-family:'Tajawal','Segoe UI',sans-serif !important; text-align:right;
}
h1 { font-size:1.45rem !important; margin-bottom:0 !important; }
h3, h4 { font-size:1.05rem !important; }

.block-container { padding:0.8rem 0.9rem 3rem 0.9rem !important; max-width:100% !important; }

section[data-testid="stSidebar"] { background: var(--ink); }
section[data-testid="stSidebar"] * { color:#E8EEF6 !important; }

div[data-testid="stMetric"] {
background:#FFF; border:1px solid #E3DCCC; border-right:4px solid var(--brass);
border-radius:12px; padding:10px 12px;
}
div[data-testid="stMetricLabel"] p { color:var(--muted) !important; font-size:0.78rem !important; }
div[data-testid="stMetricValue"] { direction:ltr; text-align:right; font-size:1.1rem !important; }
div[data-testid="stMetricDelta"] { direction:ltr; justify-content:flex-end; font-size:0.85rem !important; }

.stButton button, .stDownloadButton button {
width:100%; min-height:44px; border-radius:12px; font-weight:700;
}
input { min-height:44px !important; font-size:1rem !important; }

.stTabs [data-baseweb="tab-list"] { flex-direction:row-reverse; gap:4px; }
.stTabs [data-baseweb="tab"] { padding:8px 14px; font-size:0.95rem; }

.card { background:#FFF; border:1px solid #E3DCCC; border-radius:12px;
padding:12px 14px; margin-bottom:8px; }
.card .top { display:flex; justify-content:space-between; align-items:baseline; }
.card .nm { font-weight:700; font-size:1rem; color:var(--ink); }
.card .cd { color:var(--muted); font-size:0.8rem; direction:ltr; }
.card .rw { display:flex; justify-content:space-between; font-size:0.85rem;
color:var(--muted); margin-top:6px; }
.card .val { color:var(--ink); direction:ltr; }
.pl-up { color:var(--up); font-weight:700; direction:ltr; }
.pl-dn { color:var(--down); font-weight:700; direction:ltr; }

.verdict { border-radius:12px; padding:12px 14px; font-weight:700;
border:1px solid #E3DCCC; background:#FFF; font-size:1rem; }
.verdict small { font-weight:400; color:var(--muted); display:block;
margin-top:6px; font-size:0.8rem; line-height:1.6; }
.note { font-size:0.78rem; color:var(--muted); border-top:1px dashed #D6CDB8;
padding-top:8px; margin-top:10px; line-height:1.7; }
</style>
"""

PLOT_LAYOUT = dict(
    font=dict(family="Tajawal, sans-serif", size=12, color="#0E1B2C"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=30, b=10),
    height=300,
    dragmode=False,
    legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
)


def html(markup: str) -> None:
    """يعرض HTML بعد إزالة أي مسافات بادئة قد تجعل Markdown يعامله كنص."""
    st.markdown(" ".join(line.strip() for line in markup.strip().splitlines()),
                unsafe_allow_html=True)


# ==========================================================
# أدوات
# ==========================================================

def clean_code(raw) -> str:
    s = str(raw).strip().upper().replace("TADAWUL:", "").replace(".SR", "")
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits or s


def is_num(x) -> bool:
    try:
        return x is not None and not isinstance(x, bool) and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def fmt(x, d: int = 2, suffix: str = "", dash: str = "—") -> str:
    return f"{float(x):,.{d}f}{suffix}" if is_num(x) else dash


def money(x, dash: str = "—") -> str:
    if not is_num(x):
        return dash
    v = float(x)
    a = abs(v)
    if a >= 1e9:
        return f"{v/1e9:,.2f} مليار"
    if a >= 1e6:
        return f"{v/1e6:,.2f} مليون"
    if a >= 1e5:
        return f"{v/1e3:,.0f} ألف"
    return f"{v:,.2f}"


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_stock(code: str) -> dict:
    sym = f"{code}.SR"
    nm, sc = TADAWUL_MAP.get(code, (None, None))
    out = {"code": code, "symbol": sym, "name": nm or code, "sector": sc or "غير مصنف",
           "price": None, "prev_close": None, "error": None}
    try:
        tk = yf.Ticker(sym)
        try:
            info = tk.info or {}
        except Exception:
            info = {}

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev = info.get("previousClose")
        if not is_num(price):
            h = tk.history(period="5d")
            if not h.empty:
                price = float(h["Close"].iloc[-1])
                if len(h) > 1:
                    prev = float(h["Close"].iloc[-2])

        dy = info.get("dividendYield")
        dy = (float(dy) * 100 if float(dy) < 1 else float(dy)) if is_num(dy) else None
        roe = info.get("returnOnEquity")
        roe = float(roe) * 100 if is_num(roe) else None
        pm = info.get("profitMargins")
        pm = float(pm) * 100 if is_num(pm) else None

        out.update({
            "name": nm or info.get("longName") or info.get("shortName") or code,
            "sector": sc or info.get("sector") or "غير مصنف",
            "price": float(price) if is_num(price) else None,
            "prev_close": float(prev) if is_num(prev) else None,
            "pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb": info.get("priceToBook"),
            "dividend_yield": dy,
            "roe": roe,
            "eps": info.get("trailingEps"),
            "market_cap": info.get("marketCap"),
            "profit_margin": pm,
        })
    except Exception as exc:
        out["error"] = str(exc)
    return out


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_financials(code: str, quarterly: bool = False) -> pd.DataFrame:
    tk = yf.Ticker(f"{code}.SR")
    try:
        stmt = tk.quarterly_income_stmt if quarterly else tk.income_stmt
    except Exception:
        return pd.DataFrame()
    if stmt is None or getattr(stmt, "empty", True):
        return pd.DataFrame()

    def pick(labels):
        for lb in labels:
            for idx in stmt.index:
                if str(idx).strip().lower() == lb.lower():
                    return stmt.loc[idx]
        return None

    rev = pick(["Total Revenue", "Operating Revenue", "Revenue"])
    net = pick(["Net Income", "Net Income Common Stockholders",
                "Net Income From Continuing Operation Net Minority Interest"])
    if rev is None and net is None:
        return pd.DataFrame()

    cols = list(stmt.columns)[: 6 if quarterly else 4]
    rows = [{
        "الفترة": pd.to_datetime(c).strftime("%y-%m" if quarterly else "%Y"),
        "الإيرادات": float(rev[c]) if rev is not None and is_num(rev[c]) else None,
        "صافي الربح": float(net[c]) if net is not None and is_num(net[c]) else None,
    } for c in cols]
    return pd.DataFrame(rows).iloc[::-1].reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_tv(code: str, interval: str) -> dict:
    if not TV_AVAILABLE:
        return {"error": "مكتبة tradingview_ta غير مثبتة"}
    last = None
    for scr in TV_SCREENERS:
        try:
            a = TA_Handler(symbol=code, screener=scr, exchange=TV_EXCHANGE,
                           interval=interval).get_analysis()
            return {"summary": a.summary,
                    "oscillators": a.oscillators.get("RECOMMENDATION"),
                    "moving_averages": a.moving_averages.get("RECOMMENDATION"),
                    "indicators": a.indicators, "error": None}
        except Exception as exc:
            last = str(exc)
    return {"error": last or "تعذر جلب التحليل الفني"}


TV_AR = {
    "STRONG_BUY": ("شراء قوي", "#1E8E5A"),
    "BUY": ("شراء", "#4CAF7D"),
    "NEUTRAL": ("حياد", "#7A8899"),
    "SELL": ("بيع", "#E07A6B"),
    "STRONG_SELL": ("بيع قوي", "#C0392B"),
}


# ==========================================================
# التقييم الأساسي
# ==========================================================

def fundamental_score(d: dict):
    score, reasons = 0, []

    pe = d.get("pe")
    if is_num(pe):
        if pe <= 0:
            score -= 2; reasons.append(f"مكرر ربحية سالب ({fmt(pe)}) — خسائر")
        elif pe < 12:
            score += 2; reasons.append(f"مكرر ربحية منخفض ({fmt(pe)})")
        elif pe < 20:
            score += 1; reasons.append(f"مكرر ربحية معتدل ({fmt(pe)})")
        elif pe < 30:
            reasons.append(f"مكرر ربحية مرتفع نسبياً ({fmt(pe)})")
        else:
            score -= 2; reasons.append(f"مكرر ربحية مرتفع جداً ({fmt(pe)})")
    else:
        reasons.append("مكرر الربحية غير متاح")

    pb = d.get("pb")
    if is_num(pb):
        if pb < 1.5:
            score += 2; reasons.append(f"مضاعف دفتري منخفض ({fmt(pb)})")
        elif pb < 3:
            score += 1; reasons.append(f"مضاعف دفتري معتدل ({fmt(pb)})")
        elif pb < 5:
            reasons.append(f"مضاعف دفتري مرتفع ({fmt(pb)})")
        else:
            score -= 1; reasons.append(f"مضاعف دفتري مرتفع جداً ({fmt(pb)})")

    roe = d.get("roe")
    if is_num(roe):
        if roe >= 18:
            score += 2; reasons.append(f"عائد قوي على حقوق المساهمين ({fmt(roe,1,'%')})")
        elif roe >= 10:
            score += 1; reasons.append(f"عائد مقبول على حقوق المساهمين ({fmt(roe,1,'%')})")
        elif roe > 0:
            reasons.append(f"عائد ضعيف على حقوق المساهمين ({fmt(roe,1,'%')})")
        else:
            score -= 2; reasons.append("عائد سالب على حقوق المساهمين")

    dy = d.get("dividend_yield")
    if is_num(dy):
        if dy >= 5:
            score += 2; reasons.append(f"توزيعات مرتفعة ({fmt(dy,2,'%')})")
        elif dy >= 3:
            score += 1; reasons.append(f"توزيعات جيدة ({fmt(dy,2,'%')})")
        elif dy > 0:
            reasons.append(f"توزيعات متواضعة ({fmt(dy,2,'%')})")

    if score >= 5:
        return "قيمة جاذبة", "#1E8E5A", reasons
    if score >= 2:
        return "تسعير عادل مع ميل إيجابي", "#4CAF7D", reasons
    if score >= 0:
        return "تسعير عادل / محايد", "#7A8899", reasons
    if score >= -2:
        return "مقيّم بأعلى من حقه نسبياً", "#E07A6B", reasons
    return "مبالغ في تقييمه أو ضعيف مالياً", "#C0392B", reasons


# ==========================================================
# إدخال المحفظة
# ==========================================================

def sidebar() -> str:
    if "rows" not in st.session_state:
        st.session_state.rows = [dict(r) for r in DEFAULT_ROWS]

    st.sidebar.markdown("## ➕ إضافة سهم")
    with st.sidebar.form("add", clear_on_submit=True):
        code = st.text_input("رمز السهم", placeholder="2222")
        buy = st.number_input("سعر الشراء", min_value=0.0, step=0.05, format="%.2f")
        qty = st.number_input("عدد الأسهم", min_value=0.0, step=1.0, format="%.0f")
        submitted = st.form_submit_button("إضافة إلى المحفظة")
    if submitted:
        c = clean_code(code)
        if c and qty > 0:
            st.session_state.rows.append({"code": c, "buy": float(buy), "qty": float(qty)})
            st.sidebar.success(f"أُضيف {c}")
        else:
            st.sidebar.error("أدخل رمزاً وعدد أسهم أكبر من صفر.")

    st.sidebar.markdown("---")
    label = st.sidebar.selectbox("الإطار الزمني الفني",
                                 ["يومي", "أسبوعي", "شهري", "4 ساعات"], index=0)
    interval = {
        "يومي": Interval.INTERVAL_1_DAY if TV_AVAILABLE else "1d",
        "أسبوعي": Interval.INTERVAL_1_WEEK if TV_AVAILABLE else "1W",
        "شهري": Interval.INTERVAL_1_MONTH if TV_AVAILABLE else "1M",
        "4 ساعات": Interval.INTERVAL_4_HOURS if TV_AVAILABLE else "4h",
    }[label]

    if st.sidebar.button("🔄 تحديث الأسعار"):
        st.cache_data.clear()
        st.rerun()

    with st.sidebar.expander("نسخة احتياطية (CSV)"):
        up = st.file_uploader("استيراد", type=["csv"], label_visibility="collapsed")
        if up is not None:
            try:
                df = pd.read_csv(up)
                st.session_state.rows = [
                    {"code": clean_code(r["الرمز"]), "buy": float(r["سعر الشراء"]),
                     "qty": float(r["عدد الأسهم"])}
                    for _, r in df.iterrows()
                ]
                st.success("تم الاستيراد")
            except Exception:
                st.error("الأعمدة المطلوبة: الرمز، سعر الشراء، عدد الأسهم")
        if st.session_state.rows:
            out = pd.DataFrame([{"الرمز": r["code"], "سعر الشراء": r["buy"],
                                 "عدد الأسهم": r["qty"]} for r in st.session_state.rows])
            st.download_button("تصدير", out.to_csv(index=False).encode("utf-8-sig"),
                               "portfolio.csv", "text/csv")

    st.sidebar.caption("البيانات من Yahoo Finance و TradingView (غير رسمية) وقد تكون "
                       "ناقصة أو متأخرة. أداة متابعة — ليست توصية.")
    return interval


def build_portfolio() -> pd.DataFrame:
    recs = []
    for i, r in enumerate(st.session_state.rows):
        code = clean_code(r["code"])
        if not code:
            continue
        d = fetch_stock(code)
        price, qty, buy = d.get("price"), float(r["qty"]), float(r["buy"])
        cost = buy * qty
        value = price * qty if is_num(price) else None
        pl = value - cost if value is not None else None
        recs.append({
            "i": i, "code": code, "name": d["name"], "sector": d["sector"],
            "qty": qty, "buy": buy, "price": price, "cost": cost,
            "value": value, "pl": pl,
            "pct": (pl / cost * 100) if (pl is not None and cost > 0) else None,
        })
    return pd.DataFrame(recs)


# ==========================================================
# الأقسام
# ==========================================================

def section_overview(pf: pd.DataFrame) -> None:
    total_cost = float(pf["cost"].sum())
    total_value = float(pf["value"].sum(skipna=True))
    pl = total_value - total_cost
    pct = (pl / total_cost * 100) if total_cost else 0.0
    missing = int(pf["price"].isna().sum())

    a, b = st.columns(2)
    a.metric("القيمة الحالية", f"{money(total_value)} ر.س")
    b.metric("التكلفة", f"{money(total_cost)} ر.س")
    c, e = st.columns(2)
    c.metric("الربح / الخسارة", f"{money(pl)} ر.س", f"{pct:+.2f}%")
    e.metric("عدد الشركات", f"{len(pf)}")

    if missing:
        st.warning(f"تعذّر جلب سعر {missing} من الأسهم — استُثنيت من القيمة.")

    st.markdown("### أسهمي")
    for _, r in pf.iterrows():
        has_pl = r["pl"] is not None and not pd.isna(r["pl"])
        cls = "pl-up" if (has_pl and r["pl"] >= 0) else "pl-dn"
        pl_txt = f"{r['pl']:+,.0f} ر.س ({r['pct']:+.1f}%)" if has_pl else "غير متاح"
        html(
            f'<div class="card">'
            f'<div class="top"><span class="nm">{r["name"]}</span>'
            f'<span class="cd">{r["code"]}</span></div>'
            f'<div class="rw"><span>السعر الحالي</span>'
            f'<span class="val">{fmt(r["price"])} ر.س</span></div>'
            f'<div class="rw"><span>الشراء × الكمية</span>'
            f'<span class="val">{r["buy"]:,.2f} × {r["qty"]:,.0f}</span></div>'
            f'<div class="rw"><span>القيمة</span>'
            f'<span class="val">{money(r["value"])} ر.س</span></div>'
            f'<div class="rw"><span>الربح / الخسارة</span>'
            f'<span class="{cls}">{pl_txt}</span></div>'
            f'</div>'
        )
        if st.button("حذف", key=f"del_{r['i']}_{r['code']}"):
            st.session_state.rows.pop(int(r["i"]))
            st.rerun()

    sec = (pf.dropna(subset=["value"]).groupby("sector", as_index=False)["value"].sum()
             .sort_values("value", ascending=False))
    if not sec.empty:
        st.markdown("### التوزيع القطاعي")
        fig = go.Figure(go.Pie(
            labels=sec["sector"], values=sec["value"], hole=0.55,
            marker=dict(colors=SECTOR_COLORS[: len(sec)]),
            textinfo="percent", textposition="inside",
            hovertemplate="%{label}: %{percent}<extra></extra>",
        ))
        fig.update_layout(**PLOT_LAYOUT)
        st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)


def section_fundamentals(d: dict) -> None:
    st.markdown("### التحليل الأساسي")
    a, b = st.columns(2)
    a.metric("مكرر الربحية P/E", fmt(d.get("pe")))
    b.metric("المضاعف الدفتري P/B", fmt(d.get("pb")))
    c, e = st.columns(2)
    c.metric("عائد التوزيعات", fmt(d.get("dividend_yield"), 2, "%"))
    e.metric("العائد على حقوق المساهمين", fmt(d.get("roe"), 1, "%"))

    with st.expander("مؤشرات إضافية"):
        f, g = st.columns(2)
        f.metric("ربحية السهم EPS", fmt(d.get("eps")))
        mc = d.get("market_cap")
        g.metric("القيمة السوقية", f"{money(mc)} ر.س" if is_num(mc) else "—")
        h, k = st.columns(2)
        h.metric("هامش صافي الربح", fmt(d.get("profit_margin"), 1, "%"))
        k.metric("المكرر المتوقع", fmt(d.get("forward_pe")))

    verdict, color, reasons = fundamental_score(d)
    html(
        f'<div class="verdict" style="border-right:6px solid {color}; color:{color}">'
        f'التقييم: {verdict}'
        f'<small>{" • ".join(reasons) if reasons else "بيانات غير كافية"}</small>'
        f'<small>نموذج نقاط إرشادي بعتبات ثابتة — ليس توصية.</small></div>'
    )


def section_financials(code: str) -> None:
    st.markdown("### القوائم المالية")
    q = st.toggle("عرض ربع سنوي", key=f"q_{code}")
    df = fetch_financials(code, quarterly=q)

    if df.empty or df[["الإيرادات", "صافي الربح"]].isna().all().all():
        st.info("القوائم المالية غير متاحة لهذا الرمز عبر Yahoo Finance. "
                "راجع تقارير الشركة على موقع تداول.")
        return

    fig = go.Figure()
    fig.add_bar(name="الإيرادات", x=df["الفترة"], y=df["الإيرادات"] / 1e9, marker_color="#0E4D64")
    fig.add_bar(name="صافي الربح", x=df["الفترة"], y=df["صافي الربح"] / 1e9, marker_color="#C08A2E")
    fig.update_layout(barmode="group", yaxis_title="مليار ر.س", **PLOT_LAYOUT)
    st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)

    g = df.copy()
    g["نمو الإيرادات"] = g["الإيرادات"].pct_change() * 100
    g["نمو الأرباح"] = g["صافي الربح"].pct_change() * 100
    for _, r in g.iloc[::-1].iterrows():
        html(
            f'<div class="card">'
            f'<div class="top"><span class="nm">{r["الفترة"]}</span></div>'
            f'<div class="rw"><span>الإيرادات</span>'
            f'<span class="val">{money(r["الإيرادات"])}</span></div>'
            f'<div class="rw"><span>صافي الربح</span>'
            f'<span class="val">{money(r["صافي الربح"])}</span></div>'
            f'<div class="rw"><span>نمو الإيرادات / الأرباح</span>'
            f'<span class="val">{fmt(r["نمو الإيرادات"],1,"%")} / '
            f'{fmt(r["نمو الأرباح"],1,"%")}</span></div>'
            f'</div>'
        )


def section_technical(code: str, interval: str) -> None:
    st.markdown("### النظرة الفنية (TradingView)")
    tv = fetch_tv(code, interval)
    if tv.get("error"):
        st.info(f"تعذّر جلب التحليل الفني: {tv['error']}")
        return

    s = tv["summary"]
    label, color = TV_AR.get(s.get("RECOMMENDATION", "NEUTRAL"), ("—", "#7A8899"))
    html(
        f'<div class="verdict" style="border-right:6px solid {color}; color:{color}; font-size:1.15rem">'
        f'التوصية الفنية: {label}'
        f'<small>شراء {s.get("BUY", 0)} • حياد {s.get("NEUTRAL", 0)} • '
        f'بيع {s.get("SELL", 0)}</small></div>'
    )

    a, b = st.columns(2)
    a.metric("المذبذبات", TV_AR.get(tv.get("oscillators"), ("—", ""))[0])
    b.metric("المتوسطات", TV_AR.get(tv.get("moving_averages"), ("—", ""))[0])

    fig = go.Figure(go.Bar(
        x=[s.get("BUY", 0), s.get("NEUTRAL", 0), s.get("SELL", 0)],
        y=["شراء", "حياد", "بيع"], orientation="h",
        marker_color=["#1E8E5A", "#7A8899", "#C0392B"],
        text=[s.get("BUY", 0), s.get("NEUTRAL", 0), s.get("SELL", 0)], textposition="auto"))
    layout = dict(PLOT_LAYOUT)
    layout["height"] = 220
    layout["showlegend"] = False
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)

    ind = tv.get("indicators") or {}
    keys = {"RSI": "القوة النسبية RSI", "MACD.macd": "MACD",
            "EMA50": "متوسط EMA50", "SMA200": "متوسط SMA200"}
    picked = {v: ind.get(k) for k, v in keys.items() if is_num(ind.get(k))}
    if picked:
        with st.expander("مؤشرات فنية"):
            for k, v in picked.items():
                html(f'<div style="display:flex;justify-content:space-between;font-size:0.9rem">'
                     f'<span>{k}</span><span style="direction:ltr">{fmt(v)}</span></div>')

    st.caption("التحليل الفني عنصر توقيت داعم فقط — القرار مبني على التحليل الأساسي.")


# ==========================================================
# التشغيل
# ==========================================================

def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("محفظتي — تداول")
    st.caption(f"الجلسة: {datetime.now():%Y-%m-%d %H:%M} • اضغط » أعلى الشاشة لإضافة سهم")

    interval = sidebar()

    if not st.session_state.rows:
        st.info("لا توجد أسهم. افتح القائمة (») وأضف سهماً.")
        return

    with st.spinner("جاري جلب البيانات..."):
        pf = build_portfolio()

    if pf.empty:
        st.error("لا توجد رموز صالحة. استخدم الرمز الرقمي مثل 2222.")
        return

    t1, t2 = st.tabs(["المحفظة", "تحليل سهم"])

    with t1:
        section_overview(pf)

    with t2:
        codes = pf["code"].tolist()
        labels = dict(zip(pf["code"], pf["name"]))
        code = st.selectbox("السهم", codes, format_func=lambda c: f"{labels.get(c, c)} ({c})")
        d = fetch_stock(code)

        price, prev = d.get("price"), d.get("prev_close")
        chg = ((price - prev) / prev * 100) if (is_num(price) and is_num(prev) and prev) else None
        st.markdown(f"#### {d['name']} — {d['sector']}")
        st.metric("السعر الحالي", f"{fmt(price)} ر.س",
                  f"{chg:+.2f}%" if chg is not None else None)

        section_fundamentals(d)
        section_financials(code)
        section_technical(code, interval)


if __name__ == "__main__":
    main()
