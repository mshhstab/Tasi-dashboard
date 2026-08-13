# -*- coding: utf-8 -*-
"""
لوحة تحكم تفاعلية لمتابعة محفظة أسهم السوق السعودي (تداول - TASI)
التركيز: التحليل الأساسي (Fundamental) + النظرة الفنية من TradingView كعنصر داعم.

التشغيل:
    streamlit run tasi_dashboard.py

تنبيه: البيانات مصدرها Yahoo Finance و TradingView (غير رسمية) وقد تكون ناقصة
أو متأخرة لأسهم تداول. تحقق دائماً من موقع تداول / تقارير الشركة قبل أي قرار.
"""

from __future__ import annotations

import math
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import yfinance as yf

try:
    from tradingview_ta import TA_Handler, Interval
    TV_AVAILABLE = True
except Exception:  # pragma: no cover
    TV_AVAILABLE = False


# ==========================================================
# 1) إعدادات عامة
# ==========================================================

st.set_page_config(
    page_title="محفظتي | تداول",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# شاشات TradingView المحتملة للسوق السعودي (تُجرّب بالترتيب)
TV_SCREENERS = ["ksa", "saudiarabia", "saudi arabia"]
TV_EXCHANGE = "TADAWUL"

CACHE_TTL = 900  # 15 دقيقة

# خريطة مبدئية للأسماء والقطاعات (قابلة للتعديل — راجعها قبل الاعتماد عليها).
# إذا لم يوجد الرمز هنا يتم الرجوع تلقائياً لبيانات Yahoo Finance.
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

DEFAULT_PORTFOLIO = pd.DataFrame(
    [
        {"الرمز": "2222", "سعر الشراء": 27.5, "عدد الأسهم": 100},
        {"الرمز": "1120", "سعر الشراء": 78.0, "عدد الأسهم": 50},
        {"الرمز": "7010", "سعر الشراء": 40.0, "عدد الأسهم": 60},
    ]
)


# ==========================================================
# 2) التنسيق (RTL + هوية بصرية)
# ==========================================================

def inject_css() -> None:
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&family=IBM+Plex+Sans+Arabic:wght@400;600&display=swap" rel="stylesheet">
        <style>
        :root {
            --ink:      #0E1B2C;
            --ink-soft: #1C2E45;
            --sand:     #F5F1E8;
            --brass:    #C08A2E;
            --up:       #1E8E5A;
            --down:     #C0392B;
            --muted:    #7A8899;
        }

        html, body, [class*="css"], .stApp { direction: rtl; }
        .stApp { background: var(--sand); }

        h1, h2, h3, h4, h5, h6, p, div, span, label, li, td, th {
            font-family: 'Tajawal', 'IBM Plex Sans Arabic', 'Segoe UI', sans-serif !important;
            text-align: right;
        }

        section[data-testid="stSidebar"] {
            background: var(--ink);
            direction: rtl;
        }
        section[data-testid="stSidebar"] * { color: #E8EEF6 !important; }

        /* بطاقات المؤشرات */
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #E3DCCC;
            border-right: 4px solid var(--brass);
            border-radius: 10px;
            padding: 14px 16px;
        }
        div[data-testid="stMetricLabel"] p { color: var(--muted) !important; font-size: 0.85rem; }
        div[data-testid="stMetricValue"] { direction: ltr; text-align: right; }
        div[data-testid="stMetricDelta"] { direction: ltr; justify-content: flex-end; }

        .stTabs [data-baseweb="tab-list"] { flex-direction: row-reverse; gap: 6px; }
        .stDataFrame, .stTable { direction: rtl; }

        .verdict {
            border-radius: 10px;
            padding: 14px 18px;
            font-weight: 700;
            border: 1px solid #E3DCCC;
            background: #FFFFFF;
        }
        .verdict small { font-weight: 400; color: var(--muted); display: block; margin-top: 6px; }

        .note {
            font-size: 0.82rem;
            color: var(--muted);
            border-top: 1px dashed #D6CDB8;
            padding-top: 8px;
            margin-top: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


PLOT_LAYOUT = dict(
    font=dict(family="Tajawal, Segoe UI, sans-serif", size=13, color="#0E1B2C"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=50, b=30),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


# ==========================================================
# 3) أدوات مساعدة
# ==========================================================

def clean_code(raw: str) -> str:
    """يحوّل أي صيغة إدخال (1120 / 1120.SR / TADAWUL:1120) إلى الرمز الرقمي."""
    s = str(raw).strip().upper()
    s = s.replace("TADAWUL:", "").replace(".SR", "").replace(".SAU", "")
    return "".join(ch for ch in s if ch.isdigit()) or s


def yf_symbol(code: str) -> str:
    return f"{code}.SR"


def is_num(x) -> bool:
    try:
        return x is not None and not isinstance(x, bool) and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def fmt(x, digits: int = 2, suffix: str = "", dash: str = "غير متاح") -> str:
    return f"{float(x):,.{digits}f}{suffix}" if is_num(x) else dash


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_stock(code: str) -> dict:
    """يجلب السعر والنسب الأساسية من Yahoo Finance. يعيد قاموساً بقيم قد تكون None."""
    sym = yf_symbol(code)
    out = {"code": code, "symbol": sym, "error": None}
    try:
        tk = yf.Ticker(sym)
        info = {}
        try:
            info = tk.info or {}
        except Exception:
            info = {}

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev = info.get("previousClose")

        if not is_num(price):
            hist = tk.history(period="5d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                if len(hist) > 1:
                    prev = float(hist["Close"].iloc[-2])

        # yfinance يعيد عائد التوزيعات أحياناً كنسبة مئوية وأحياناً ككسر عشري
        dy = info.get("dividendYield")
        if is_num(dy):
            dy = float(dy) * 100 if float(dy) < 1 else float(dy)
        else:
            dy = None

        roe = info.get("returnOnEquity")
        roe = float(roe) * 100 if is_num(roe) else None

        name_map, sector_map = TADAWUL_MAP.get(code, (None, None))

        out.update(
            {
                "name": name_map or info.get("longName") or info.get("shortName") or code,
                "sector": sector_map or info.get("sector") or "غير مصنف",
                "price": float(price) if is_num(price) else None,
                "prev_close": float(prev) if is_num(prev) else None,
                "pe": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "pb": info.get("priceToBook"),
                "dividend_yield": dy,
                "roe": roe,
                "eps": info.get("trailingEps"),
                "market_cap": info.get("marketCap"),
                "profit_margin": (float(info["profitMargins"]) * 100
                                  if is_num(info.get("profitMargins")) else None),
                "debt_to_equity": info.get("debtToEquity"),
            }
        )
    except Exception as exc:  # الشبكة / رمز غير موجود
        out["error"] = str(exc)
        name_map, sector_map = TADAWUL_MAP.get(code, (code, "غير مصنف"))
        out.update({"name": name_map, "sector": sector_map, "price": None})
    return out


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_financials(code: str, quarterly: bool = False) -> pd.DataFrame:
    """يعيد جدول: الفترة | الإيرادات | صافي الربح (بالريال). فارغ إذا لم تتوفر البيانات."""
    tk = yf.Ticker(yf_symbol(code))
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

    revenue = pick(["Total Revenue", "Operating Revenue", "Revenue"])
    net = pick(["Net Income", "Net Income Common Stockholders",
                "Net Income From Continuing Operation Net Minority Interest"])
    if revenue is None and net is None:
        return pd.DataFrame()

    cols = list(stmt.columns)[: 4 if not quarterly else 8]
    rows = []
    for c in cols:
        rows.append(
            {
                "الفترة": pd.to_datetime(c).strftime("%Y-%m" if quarterly else "%Y"),
                "الإيرادات": float(revenue[c]) if revenue is not None and is_num(revenue[c]) else None,
                "صافي الربح": float(net[c]) if net is not None and is_num(net[c]) else None,
            }
        )
    return pd.DataFrame(rows).iloc[::-1].reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_tv(code: str, interval: str) -> dict:
    """التوصية الفنية المجملة من TradingView. يجرب أكثر من اسم screener."""
    if not TV_AVAILABLE:
        return {"error": "مكتبة tradingview_ta غير مثبتة"}
    last_err = None
    for scr in TV_SCREENERS:
        try:
            h = TA_Handler(symbol=code, screener=scr, exchange=TV_EXCHANGE, interval=interval)
            a = h.get_analysis()
            return {
                "screener": scr,
                "summary": a.summary,
                "oscillators": a.oscillators.get("RECOMMENDATION"),
                "moving_averages": a.moving_averages.get("RECOMMENDATION"),
                "indicators": a.indicators,
                "error": None,
            }
        except Exception as exc:
            last_err = str(exc)
    return {"error": last_err or "تعذر جلب التحليل الفني"}


TV_AR = {
    "STRONG_BUY": ("شراء قوي", "#1E8E5A"),
    "BUY": ("شراء", "#4CAF7D"),
    "NEUTRAL": ("حياد", "#7A8899"),
    "SELL": ("بيع", "#E07A6B"),
    "STRONG_SELL": ("بيع قوي", "#C0392B"),
}


# ==========================================================
# 4) منطق التقييم الأساسي (نموذج نقاط بسيط وشفاف)
# ==========================================================

def fundamental_score(d: dict) -> tuple[str, str, list[str]]:
    """يعيد (التقييم، اللون، أسباب). قواعد إرشادية عامة — عدّل العتبات حسب القطاع."""
    score, reasons = 0, []

    pe = d.get("pe")
    if is_num(pe):
        if pe <= 0:
            score -= 2; reasons.append(f"مكرر ربحية سالب ({fmt(pe)}) — الشركة خاسرة")
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
            score += 2; reasons.append(f"مضاعف القيمة الدفترية منخفض ({fmt(pb)})")
        elif pb < 3:
            score += 1; reasons.append(f"مضاعف القيمة الدفترية معتدل ({fmt(pb)})")
        elif pb < 5:
            reasons.append(f"مضاعف القيمة الدفترية مرتفع ({fmt(pb)})")
        else:
            score -= 1; reasons.append(f"مضاعف القيمة الدفترية مرتفع جداً ({fmt(pb)})")

    roe = d.get("roe")
    if is_num(roe):
        if roe >= 18:
            score += 2; reasons.append(f"عائد قوي على حقوق المساهمين ({fmt(roe, 1, '%')})")
        elif roe >= 10:
            score += 1; reasons.append(f"عائد مقبول على حقوق المساهمين ({fmt(roe, 1, '%')})")
        elif roe > 0:
            reasons.append(f"عائد ضعيف على حقوق المساهمين ({fmt(roe, 1, '%')})")
        else:
            score -= 2; reasons.append("عائد سالب على حقوق المساهمين")

    dy = d.get("dividend_yield")
    if is_num(dy):
        if dy >= 5:
            score += 2; reasons.append(f"عائد توزيعات مرتفع ({fmt(dy, 2, '%')})")
        elif dy >= 3:
            score += 1; reasons.append(f"عائد توزيعات جيد ({fmt(dy, 2, '%')})")
        elif dy > 0:
            reasons.append(f"عائد توزيعات متواضع ({fmt(dy, 2, '%')})")

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
# 5) الشريط الجانبي — إدخال المحفظة
# ==========================================================

def sidebar() -> tuple[pd.DataFrame, str]:
    st.sidebar.markdown("## 💼 محفظتي")
    st.sidebar.caption("أدخل الرمز الرقمي للسهم (مثال: 2222) أو 2222.SR")

    if "portfolio" not in st.session_state:
        st.session_state.portfolio = DEFAULT_PORTFOLIO.copy()

    up = st.sidebar.file_uploader("استيراد محفظة (CSV)", type=["csv"])
    if up is not None:
        try:
            df = pd.read_csv(up)
            if {"الرمز", "سعر الشراء", "عدد الأسهم"}.issubset(df.columns):
                st.session_state.portfolio = df
                st.sidebar.success("تم استيراد الملف")
            else:
                st.sidebar.error("الأعمدة المطلوبة: الرمز، سعر الشراء، عدد الأسهم")
        except Exception as exc:
            st.sidebar.error(f"تعذّر قراءة الملف: {exc}")

    edited = st.sidebar.data_editor(
        st.session_state.portfolio,
        num_rows="dynamic",
        use_container_width=True,
        key="editor",
        column_config={
            "الرمز": st.column_config.TextColumn("الرمز", required=True),
            "سعر الشراء": st.column_config.NumberColumn("سعر الشراء", min_value=0.0, step=0.05, format="%.2f"),
            "عدد الأسهم": st.column_config.NumberColumn("عدد الأسهم", min_value=0, step=1),
        },
    )
    st.session_state.portfolio = edited

    st.sidebar.download_button(
        "تصدير المحفظة (CSV)",
        edited.to_csv(index=False).encode("utf-8-sig"),
        file_name="portfolio.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.sidebar.markdown("---")
    interval_label = st.sidebar.selectbox(
        "الإطار الزمني للتحليل الفني",
        ["يومي", "أسبوعي", "شهري", "4 ساعات", "ساعة"],
        index=0,
    )
    interval = {
        "يومي": Interval.INTERVAL_1_DAY if TV_AVAILABLE else "1d",
        "أسبوعي": Interval.INTERVAL_1_WEEK if TV_AVAILABLE else "1W",
        "شهري": Interval.INTERVAL_1_MONTH if TV_AVAILABLE else "1M",
        "4 ساعات": Interval.INTERVAL_4_HOURS if TV_AVAILABLE else "4h",
        "ساعة": Interval.INTERVAL_1_HOUR if TV_AVAILABLE else "1h",
    }[interval_label]

    if st.sidebar.button("🔄 تحديث البيانات", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown(
        "<div class='note'>البيانات من Yahoo Finance و TradingView (مصادر غير رسمية). "
        "قد تكون ناقصة أو متأخرة لأسهم تداول. هذه اللوحة أداة متابعة وليست توصية استثمارية.</div>",
        unsafe_allow_html=True,
    )
    return edited, interval


# ==========================================================
# 6) بناء بيانات المحفظة
# ==========================================================

def build_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        code = clean_code(r.get("الرمز", ""))
        if not code:
            continue
        try:
            qty = float(r.get("عدد الأسهم") or 0)
            buy = float(r.get("سعر الشراء") or 0)
        except (TypeError, ValueError):
            continue

        d = fetch_stock(code)
        price = d.get("price")
        cost = buy * qty
        value = price * qty if is_num(price) else None
        pl = value - cost if value is not None else None

        rows.append(
            {
                "الرمز": code,
                "الشركة": d.get("name"),
                "القطاع": d.get("sector"),
                "عدد الأسهم": qty,
                "سعر الشراء": buy,
                "السعر الحالي": price,
                "التكلفة": cost,
                "القيمة الحالية": value,
                "الربح/الخسارة": pl,
                "العائد %": (pl / cost * 100) if (pl is not None and cost > 0) else None,
                "مكرر الربحية": d.get("pe"),
                "القيمة الدفترية": d.get("pb"),
                "عائد التوزيعات %": d.get("dividend_yield"),
                "العائد على حقوق المساهمين %": d.get("roe"),
            }
        )
    return pd.DataFrame(rows)


# ==========================================================
# 7) الأقسام
# ==========================================================

def section_overview(pf: pd.DataFrame) -> None:
    st.subheader("أولاً: ملخص المحفظة")

    total_cost = pf["التكلفة"].sum()
    total_value = pf["القيمة الحالية"].sum(skipna=True)
    pl = total_value - total_cost
    pl_pct = (pl / total_cost * 100) if total_cost else 0
    missing = int(pf["السعر الحالي"].isna().sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("القيمة السوقية الحالية", f"{total_value:,.2f} ر.س")
    c2.metric("إجمالي التكلفة", f"{total_cost:,.2f} ر.س")
    c3.metric("الربح / الخسارة", f"{pl:,.2f} ر.س", f"{pl_pct:+.2f}%")
    c4.metric("عدد الشركات", f"{len(pf)}")

    if missing:
        st.warning(f"تعذّر جلب السعر الحالي لـ {missing} من الأسهم — استُثنيت من القيمة السوقية.")

    left, right = st.columns([1, 1])

    with left:
        sec = (pf.dropna(subset=["القيمة الحالية"])
                 .groupby("القطاع", as_index=False)["القيمة الحالية"].sum()
                 .sort_values("القيمة الحالية", ascending=False))
        if not sec.empty:
            fig = px.pie(sec, values="القيمة الحالية", names="القطاع", hole=0.55,
                         color_discrete_sequence=px.colors.sequential.Aggrnyl)
            fig.update_traces(textposition="inside", texttemplate="%{label}<br>%{percent}")
            fig.update_layout(title="التوزيع القطاعي", **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

    with right:
        d = pf.dropna(subset=["الربح/الخسارة"]).sort_values("الربح/الخسارة")
        if not d.empty:
            fig = go.Figure(go.Bar(
                x=d["الربح/الخسارة"], y=d["الشركة"], orientation="h",
                marker_color=["#C0392B" if v < 0 else "#1E8E5A" for v in d["الربح/الخسارة"]],
                text=[f"{v:,.0f}" for v in d["الربح/الخسارة"]], textposition="auto",
            ))
            fig.update_layout(title="الربح / الخسارة لكل سهم (ر.س)", **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

    show = pf.copy()
    st.dataframe(
        show.style.format({
            "سعر الشراء": "{:,.2f}", "السعر الحالي": "{:,.2f}",
            "التكلفة": "{:,.2f}", "القيمة الحالية": "{:,.2f}",
            "الربح/الخسارة": "{:,.2f}", "العائد %": "{:+.2f}",
            "مكرر الربحية": "{:,.2f}", "القيمة الدفترية": "{:,.2f}",
            "عائد التوزيعات %": "{:,.2f}", "العائد على حقوق المساهمين %": "{:,.2f}",
            "عدد الأسهم": "{:,.0f}",
        }, na_rep="—"),
        use_container_width=True,
    )


def section_fundamentals(d: dict) -> None:
    st.subheader("ثانياً: بطاقة التحليل الأساسي")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("مكرر الربحية P/E", fmt(d.get("pe")))
    c2.metric("مضاعف القيمة الدفترية P/B", fmt(d.get("pb")))
    c3.metric("عائد التوزيعات", fmt(d.get("dividend_yield"), 2, "%"))
    c4.metric("العائد على حقوق المساهمين ROE", fmt(d.get("roe"), 1, "%"))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("ربحية السهم EPS", fmt(d.get("eps")))
    mc = d.get("market_cap")
    c6.metric("القيمة السوقية", f"{mc/1e9:,.2f} مليار ر.س" if is_num(mc) else "غير متاح")
    c7.metric("هامش صافي الربح", fmt(d.get("profit_margin"), 1, "%"))
    c8.metric("مكرر الربحية المتوقع", fmt(d.get("forward_pe")))

    verdict, color, reasons = fundamental_score(d)
    st.markdown(
        f"<div class='verdict' style='border-right:6px solid {color}; color:{color}'>"
        f"التقييم الملخص: {verdict}"
        f"<small>{' • '.join(reasons) if reasons else 'لا توجد بيانات كافية'}</small>"
        f"<small>نموذج نقاط إرشادي مبني على العتبات المعرّفة في الكود — ليس توصية.</small>"
        f"</div>",
        unsafe_allow_html=True,
    )


def section_financials(code: str) -> None:
    st.subheader("ثالثاً: أداء القوائم المالية")
    mode = st.radio("الفترة", ["سنوي (4 سنوات)", "ربع سنوي"], horizontal=True,
                    key=f"fin_{code}", label_visibility="collapsed")
    df = fetch_financials(code, quarterly=mode.startswith("ربع"))

    if df.empty or df[["الإيرادات", "صافي الربح"]].isna().all().all():
        st.info("القوائم المالية غير متاحة لهذا الرمز عبر Yahoo Finance. راجع تقارير الشركة على موقع تداول.")
        return

    scale, unit = 1e9, "مليار ر.س"
    fig = go.Figure()
    fig.add_bar(name="الإيرادات", x=df["الفترة"], y=df["الإيرادات"] / scale,
                marker_color="#1C2E45", text=(df["الإيرادات"] / scale).round(2), textposition="outside")
    fig.add_bar(name="صافي الربح", x=df["الفترة"], y=df["صافي الربح"] / scale,
                marker_color="#C08A2E", text=(df["صافي الربح"] / scale).round(2), textposition="outside")
    fig.update_layout(barmode="group", title=f"الإيرادات وصافي الربح ({unit})",
                      yaxis_title=unit, **PLOT_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)

    g = df.copy()
    g["نمو الإيرادات %"] = g["الإيرادات"].pct_change() * 100
    g["نمو صافي الربح %"] = g["صافي الربح"].pct_change() * 100
    g["هامش صافي الربح %"] = g["صافي الربح"] / g["الإيرادات"] * 100
    st.dataframe(
        g.style.format({
            "الإيرادات": "{:,.0f}", "صافي الربح": "{:,.0f}",
            "نمو الإيرادات %": "{:+.1f}", "نمو صافي الربح %": "{:+.1f}",
            "هامش صافي الربح %": "{:.1f}",
        }, na_rep="—"),
        use_container_width=True,
    )


def section_technical(code: str, interval: str) -> None:
    st.subheader("رابعاً: النظرة الفنية المجملة (TradingView)")
    tv = fetch_tv(code, interval)

    if tv.get("error"):
        st.info(f"تعذّر جلب التحليل الفني: {tv['error']}")
        return

    summary = tv["summary"]
    rec = summary.get("RECOMMENDATION", "NEUTRAL")
    label, color = TV_AR.get(rec, (rec, "#7A8899"))

    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        st.markdown(
            f"<div class='verdict' style='border-right:6px solid {color}; color:{color}; font-size:1.25rem'>"
            f"التوصية الفنية: {label}"
            f"<small>مؤشرات شراء: {summary.get('BUY', 0)} • حياد: {summary.get('NEUTRAL', 0)} • بيع: {summary.get('SELL', 0)}</small>"
            f"</div>", unsafe_allow_html=True)
    c2.metric("المذبذبات Oscillators", TV_AR.get(tv.get("oscillators"), (tv.get("oscillators") or "—", ""))[0])
    c3.metric("المتوسطات المتحركة", TV_AR.get(tv.get("moving_averages"), (tv.get("moving_averages") or "—", ""))[0])

    fig = go.Figure(go.Bar(
        x=["شراء", "حياد", "بيع"],
        y=[summary.get("BUY", 0), summary.get("NEUTRAL", 0), summary.get("SELL", 0)],
        marker_color=["#1E8E5A", "#7A8899", "#C0392B"],
        text=[summary.get("BUY", 0), summary.get("NEUTRAL", 0), summary.get("SELL", 0)],
        textposition="outside",
    ))
    fig.update_layout(title="توزيع إشارات المؤشرات الفنية", **PLOT_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)

    ind = tv.get("indicators") or {}
    keys = {"RSI": "مؤشر القوة النسبية RSI", "Stoch.K": "ستوكاستك %K",
            "MACD.macd": "MACD", "EMA50": "متوسط EMA50", "SMA200": "متوسط SMA200"}
    picked = {v: ind.get(k) for k, v in keys.items() if is_num(ind.get(k))}
    if picked:
        st.dataframe(pd.DataFrame([picked]).T.rename(columns={0: "القيمة"}).style.format("{:,.2f}"),
                     use_container_width=True)

    st.markdown("<div class='note'>التحليل الفني هنا عنصر توقيت داعم فقط — القرار مبني على التحليل الأساسي.</div>",
                unsafe_allow_html=True)


# ==========================================================
# 8) التشغيل
# ==========================================================

def main() -> None:
    inject_css()
    st.title("لوحة متابعة محفظة السوق السعودي (تداول)")
    st.caption(f"آخر تحديث للجلسة: {datetime.now():%Y-%m-%d %H:%M}")

    df_in, interval = sidebar()
    if df_in.empty:
        st.info("أضف أسهمك من الشريط الجانبي للبدء.")
        return

    with st.spinner("جاري جلب البيانات..."):
        pf = build_portfolio(df_in)

    if pf.empty:
        st.error("لا توجد رموز صالحة. استخدم الرمز الرقمي مثل 2222.")
        return

    tab1, tab2 = st.tabs(["ملخص المحفظة", "تحليل سهم"])

    with tab1:
        section_overview(pf)

    with tab2:
        options = pf["الرمز"].tolist()
        labels = {r["الرمز"]: f"{r['الرمز']} — {r['الشركة']}" for _, r in pf.iterrows()}
        code = st.selectbox("اختر السهم", options, format_func=lambda c: labels.get(c, c))
        d = fetch_stock(code)

        price, prev = d.get("price"), d.get("prev_close")
        chg = ((price - prev) / prev * 100) if (is_num(price) and is_num(prev) and prev) else None
        st.markdown(f"### {d.get('name')} — {d.get('sector')}")
        st.metric("السعر الحالي", fmt(price, 2, " ر.س"), f"{chg:+.2f}%" if chg is not None else None)

        st.divider()
        section_fundamentals(d)
        st.divider()
        section_financials(code)
        st.divider()
        section_technical(code, interval)


if __name__ == "__main__":
    main()
