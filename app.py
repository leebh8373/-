import streamlit as st
import pandas as pd
import numpy as np
import calculations as calc
from datetime import datetime
import importlib
import os
import re
from io import BytesIO

# [FORCE RELOAD] 서버 캐시 방지를 위해 모듈 강제 리로드
importlib.reload(calc)

__version__ = "6.6.0" # Excel/PDF Auto Import + Measured Data Learning Patch

# Plotly 라이브러리 가용성 체크 (에러 방지용 검증 로직)
try:
    import plotly.graph_objects as go
    IS_PLOTLY_AVAILABLE = True
except ImportError:
    IS_PLOTLY_AVAILABLE = False

# [MEASURED DATA / EMPIRICAL CALIBRATION]
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MEASURED_DB_PATH = os.path.join(DATA_DIR, "measured_property_database.csv")
PROP_KEYS = ["ys", "ts", "el", "ra", "cvn", "hb"]
ELEMENT_LIST = ['C','Si','Mn','P','S','Cr','Mo','Ni','Cu','V','Nb','Ti','Al','B','N','As','Sn','Sb','Pb','Zr']

def _measured_columns():
    base = ["timestamp", "heat_no", "material_grade", "product_name", "section_type",
            "thickness_mm", "coupon_thickness_mm", "test_temp_c",
            "p0_type", "p0_temp", "p0_time_min", "p0_cooling",
            "p1_type", "p1_temp", "p1_time_min", "p1_cooling",
            "p2_type", "p2_temp", "p2_time_min", "p2_cooling",
            "p3_type", "p3_temp", "p3_time_min", "p3_cooling"]
    comp_cols = [f"comp_{e}" for e in ELEMENT_LIST]
    prop_cols = [f"actual_{k}" for k in PROP_KEYS] + [f"pred_{k}" for k in PROP_KEYS] + [f"residual_{k}" for k in PROP_KEYS]
    return base + comp_cols + prop_cols + ["ceq_iiw", "pcm", "micro_name", "note"]

def load_measured_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    cols = _measured_columns()
    if not os.path.exists(MEASURED_DB_PATH):
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(MEASURED_DB_PATH)
    for col in cols:
        if col not in df.columns:
            df[col] = np.nan
    return df[cols]

def save_measured_db(df):
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(MEASURED_DB_PATH, index=False, encoding="utf-8-sig")

def apply_empirical_calibration(report, comp, thickness, enabled=True):
    if not enabled:
        return report, {"n": 0, "message": "실측 보정 미적용"}
    df = load_measured_db()
    if df.empty or len(df.dropna(subset=["residual_ts", "residual_ys"], how="all")) < 3:
        return report, {"n": 0, "message": "실측 데이터 3건 이상 누적 시 자동 보정 적용"}
    work = df.copy()
    for col in ["thickness_mm", "ceq_iiw", "pcm"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    eq = calc.calculate_all_equivalents(comp)
    thick = float(thickness)
    ceq = float(eq.get("ceq_iiw", 0) or 0)
    pcm = float(eq.get("pcm", 0) or 0)
    dist = (abs(work["thickness_mm"] - thick) / 350.0).fillna(1.5) + (abs(work["ceq_iiw"] - ceq) / 0.18).fillna(1.5) + (abs(work["pcm"] - pcm) / 0.08).fillna(1.0)
    weight = 1.0 / (1.0 + dist)
    calibrated = report.copy()
    offsets = {}
    used = 0
    for k in PROP_KEYS:
        rcol = f"residual_{k}"
        if rcol not in work:
            continue
        residuals = pd.to_numeric(work[rcol], errors="coerce")
        mask = residuals.notna()
        if int(mask.sum()) >= 3:
            offset = float((residuals[mask] * weight[mask]).sum() / max(float(weight[mask].sum()), 1e-9))
            limit = {"ys":60, "ts":70, "el":5, "ra":8, "cvn":25, "hb":25}[k]
            offset = max(-limit, min(limit, offset))
            calibrated[k] = round(max(0, float(report[k]) + offset), 1)
            offsets[k] = round(offset, 2)
            used = max(used, int(mask.sum()))
    calibrated["calibration_offsets"] = offsets
    return calibrated, {"n": used, "message": f"실측 데이터 기반 잔차 보정 적용: {used}건", "offsets": offsets}

def build_measured_record(heat_no, material_grade, product_name, section_type, comp, p0, p1, p2, p3, thickness, coupon_thick, test_temp, actuals, note=""):
    ts_1st = calc.calculate_1st_stage_physics(comp, p1, thickness)
    pred = calc.get_final_expert_simulation(ts_1st, p2, p3, test_temp, comp, p1=p1, thickness=thickness, p0=p0, ceq_standard=ceq_std)
    eq = calc.calculate_all_equivalents(comp)
    row = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "heat_no": heat_no, "material_grade": material_grade,
           "product_name": product_name, "section_type": section_type, "thickness_mm": thickness, "coupon_thickness_mm": coupon_thick, "test_temp_c": test_temp,
           "p0_type": p0.get("type"), "p0_temp": p0.get("temp"), "p0_time_min": p0.get("time"), "p0_cooling": p0.get("cooling"),
           "p1_type": p1.get("type"), "p1_temp": p1.get("temp"), "p1_time_min": p1.get("time"), "p1_cooling": p1.get("cooling"),
           "p2_type": p2.get("type"), "p2_temp": p2.get("temp"), "p2_time_min": p2.get("time"), "p2_cooling": p2.get("cooling"),
           "p3_type": p3.get("type"), "p3_temp": p3.get("temp"), "p3_time_min": p3.get("time"), "p3_cooling": p3.get("cooling"),
           "ceq_iiw": eq.get("ceq_iiw"), "pcm": eq.get("pcm"), "micro_name": pred.get("micro_name"), "note": note}
    for e in ELEMENT_LIST:
        row[f"comp_{e}"] = float(comp.get(e, 0) or 0)
    for k in PROP_KEYS:
        a = actuals.get(k, np.nan)
        row[f"actual_{k}"] = a
        row[f"pred_{k}"] = pred.get(k, np.nan)
        row[f"residual_{k}"] = (float(a) - float(pred.get(k, 0))) if pd.notna(a) else np.nan
    return row

def _safe_float(value, default=np.nan):
    """문자열/셀 값에서 숫자만 안전하게 추출합니다. 예: '415 MPa' -> 415.0"""
    try:
        if value is None:
            return default
        if isinstance(value, str):
            txt = value.strip().replace(",", "")
            if txt in ["", "-", "N/A", "NA", "nan", "None"]:
                return default
            m = re.search(r"[-+]?\d*\.?\d+", txt)
            if not m:
                return default
            return float(m.group(0))
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _norm_name(name):
    return re.sub(r"[^a-z0-9가-힣]+", "", str(name).strip().lower())


COLUMN_SYNONYMS = {
    "heat_no": ["heatno", "heatnumber", "heat", "용해번호", "히트번호", "lotno", "chargeno"],
    "material_grade": ["material", "grade", "spec", "standard", "재질", "규격", "강종"],
    "product_name": ["product", "item", "description", "품명", "제품명", "partname"],
    "section_type": ["section", "location", "testlocation", "position", "시험위치", "채취위치"],
    "thickness_mm": ["thickness", "thk", "tmm", "sectionthickness", "두께", "두께mm"],
    "coupon_thickness_mm": ["couponthickness", "coupont", "couponthk", "시험편두께", "coupon두께"],
    "test_temp_c": ["testtemp", "impacttemp", "cvntemp", "temperature", "시험온도", "충격시험온도"],
    "actual_ys": ["ys", "yield", "yieldstrength", "yieldstrengthmpa", "yieldmpa", "항복", "항복강도", "rp02"],
    "actual_ts": ["ts", "uts", "tensile", "tensilestrength", "tensilestrengthmpa", "인장", "인장강도", "rm"],
    "actual_el": ["el", "elongation", "elong", "a5", "연신율", "연신"],
    "actual_ra": ["ra", "reductionofarea", "reductionarea", "단면수축", "단면수축률", "z"],
    "actual_cvn": ["cvn", "impact", "charpy", "charpyv", "absorbedenergy", "impactj", "충격", "충격치", "흡수에너지"],
    "actual_hb": ["hb", "hbw", "hardness", "brinell", "경도", "브리넬"],
    "p0_type": ["p0type", "pretype", "예비공정"], "p0_temp": ["p0temp", "pretemp", "예비온도"],
    "p0_time_min": ["p0time", "pretime", "예비시간"], "p0_cooling": ["p0cooling", "precooling", "예비냉각"],
    "p1_type": ["p1type", "firsttype", "qtype", "1차공정", "quenchingtype"],
    "p1_temp": ["p1temp", "austenitizingtemp", "quenchingtemp", "1차온도", "소입온도"],
    "p1_time_min": ["p1time", "austenitizingtime", "quenchingtime", "1차시간", "소입시간"],
    "p1_cooling": ["p1cooling", "quenchingcooling", "1차냉각", "소입냉각"],
    "p2_type": ["p2type", "tempertype", "2차공정", "temperingtype"],
    "p2_temp": ["p2temp", "temperingtemp", "2차온도", "뜨임온도"],
    "p2_time_min": ["p2time", "temperingtime", "2차시간", "뜨임시간"],
    "p2_cooling": ["p2cooling", "temperingcooling", "2차냉각", "뜨임냉각"],
    "p3_type": ["p3type", "pwhttype", "srtype", "3차공정"],
    "p3_temp": ["p3temp", "pwhttemp", "srtemp", "3차온도"],
    "p3_time_min": ["p3time", "pwhttime", "srtime", "3차시간"],
    "p3_cooling": ["p3cooling", "pwhtcooling", "srcooling", "3차냉각"],
    "note": ["note", "remark", "remarks", "비고", "메모"],
}
for _e in ELEMENT_LIST:
    COLUMN_SYNONYMS[f"comp_{_e}"] = [_e.lower(), f"{_e.lower()}%", f"comp{_e.lower()}", f"chemical{_e.lower()}", f"성분{_e.lower()}"]


def _find_source_col(df, target):
    normalized = {_norm_name(c): c for c in df.columns}
    candidates = [_norm_name(target)] + [_norm_name(x) for x in COLUMN_SYNONYMS.get(target, [])]
    for cand in candidates:
        if cand in normalized:
            return normalized[cand]
    for ncol, original in normalized.items():
        for cand in candidates:
            if cand and (cand in ncol or ncol in cand):
                return original
    return None


def _standardize_import_dataframe(raw_df):
    """Excel/CSV/PDF 표를 Sentinel 누적 DB 컬럼명으로 표준화합니다."""
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=_measured_columns())
    df = raw_df.copy().dropna(how="all")
    if df.empty:
        return pd.DataFrame(columns=_measured_columns())
    df.columns = [str(c).strip() for c in df.columns]
    if set(_measured_columns()).issubset(set(df.columns)):
        return df[_measured_columns()].copy()

    out = pd.DataFrame(index=df.index)
    targets = ["heat_no", "material_grade", "product_name", "section_type", "thickness_mm", "coupon_thickness_mm", "test_temp_c",
               "p0_type", "p0_temp", "p0_time_min", "p0_cooling", "p1_type", "p1_temp", "p1_time_min", "p1_cooling",
               "p2_type", "p2_temp", "p2_time_min", "p2_cooling", "p3_type", "p3_temp", "p3_time_min", "p3_cooling",
               "note"] + [f"comp_{e}" for e in ELEMENT_LIST] + [f"actual_{k}" for k in PROP_KEYS]
    for target in targets:
        src = _find_source_col(df, target)
        out[target] = df[src] if src is not None else np.nan

    useful_cols = ["heat_no", "actual_ys", "actual_ts", "actual_cvn", "actual_hb"] + [f"comp_{e}" for e in ["C", "Si", "Mn", "Ni", "Cr", "Mo"]]
    mask = pd.Series(False, index=out.index)
    for c in useful_cols:
        mask = mask | out[c].notna()
    return out[mask].copy()


def parse_excel_or_csv(uploaded_file):
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return _standardize_import_dataframe(pd.read_csv(uploaded_file))
    sheets = pd.read_excel(uploaded_file, sheet_name=None, engine="openpyxl" if name.endswith(".xlsx") else None)
    parsed = []
    for sheet_name, sheet_df in sheets.items():
        std = _standardize_import_dataframe(sheet_df)
        if not std.empty:
            std["note"] = std.get("note", "").fillna("").astype(str) + f" | imported_sheet={sheet_name}"
            parsed.append(std)
    return pd.concat(parsed, ignore_index=True) if parsed else pd.DataFrame(columns=_measured_columns())


def _extract_pdf_text(uploaded_file):
    data = uploaded_file.read()
    uploaded_file.seek(0)
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page in pdf.pages:
                text += "\n" + (page.extract_text() or "")
    except Exception:
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            for page in reader.pages:
                text += "\n" + (page.extract_text() or "")
        except Exception:
            text = ""
    return text


def _extract_pdf_tables(uploaded_file):
    data = uploaded_file.read()
    uploaded_file.seek(0)
    tables = []
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page_no, page in enumerate(pdf.pages, start=1):
                for table in page.extract_tables() or []:
                    if len(table) >= 2:
                        header = [str(x).strip() if x is not None else "" for x in table[0]]
                        df = pd.DataFrame(table[1:], columns=header)
                        std = _standardize_import_dataframe(df)
                        if not std.empty:
                            std["note"] = std.get("note", "").fillna("").astype(str) + f" | imported_pdf_page={page_no}"
                            tables.append(std)
    except Exception:
        pass
    return tables


def parse_pdf_certificate(uploaded_file):
    """PDF MTR/시험성적서에서 표 또는 key-value 텍스트를 추출합니다."""
    table_frames = _extract_pdf_tables(uploaded_file)
    if table_frames:
        return pd.concat(table_frames, ignore_index=True)
    text = _extract_pdf_text(uploaded_file)
    if not text.strip():
        return pd.DataFrame(columns=_measured_columns())

    row = {c: np.nan for c in _measured_columns()}
    row["note"] = f"PDF 자동 추출: {uploaded_file.name}"
    patterns = {
        "heat_no": r"(?:Heat\s*(?:No\.?|Number)|용해번호|히트번호)\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
        "material_grade": r"(?:Material|Grade|Spec|재질|규격)\s*[:：]?\s*([A-Za-z0-9\-_/ .]+)",
        "thickness_mm": r"(?:Thickness|THK|두께)\s*[:：]?\s*([0-9.]+)\s*mm?",
        "actual_ys": r"(?:YS|Yield\s*Strength|항복강도|Rp0\.2)\s*[:：]?\s*([0-9.]+)",
        "actual_ts": r"(?:TS|UTS|Tensile\s*Strength|인장강도|Rm)\s*[:：]?\s*([0-9.]+)",
        "actual_el": r"(?:EL|Elongation|연신율|A5)\s*[:：]?\s*([0-9.]+)",
        "actual_ra": r"(?:RA|Reduction\s*of\s*Area|단면수축률|Z)\s*[:：]?\s*([0-9.]+)",
        "actual_cvn": r"(?:CVN|Charpy|Impact|충격치|흡수에너지)\s*[:：]?\s*([0-9.]+)",
        "actual_hb": r"(?:HBW?|Brinell|Hardness|경도)\s*[:：]?\s*([0-9.]+)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            row[key] = m.group(1).strip()
    for e in ELEMENT_LIST:
        m = re.search(rf"\b{re.escape(e)}\b\s*[:：]?\s*([0-9]+\.?[0-9]*)", text, flags=re.IGNORECASE)
        if m:
            row[f"comp_{e}"] = m.group(1)
    return _standardize_import_dataframe(pd.DataFrame([row]))


def _complete_import_rows(parsed_df, default_meta=None):
    """추출된 표준 컬럼을 예측 잔차가 포함된 누적 DB 레코드로 변환합니다."""
    default_meta = default_meta or {}
    rows = []
    for _, r in parsed_df.iterrows():
        comp = {e: _safe_float(r.get(f"comp_{e}"), 0.0) for e in ELEMENT_LIST}
        actuals = {k: _safe_float(r.get(f"actual_{k}"), np.nan) for k in PROP_KEYS}
        if all(pd.isna(v) for v in actuals.values()):
            continue
        p0 = {"type": str(r.get("p0_type") if pd.notna(r.get("p0_type")) else default_meta.get("p0_type", "None")),
              "temp": _safe_float(r.get("p0_temp"), default_meta.get("p0_temp", 950)),
              "time": _safe_float(r.get("p0_time_min"), default_meta.get("p0_time_min", 240)),
              "cooling": str(r.get("p0_cooling") if pd.notna(r.get("p0_cooling")) else default_meta.get("p0_cooling", "공냉(AC)"))}
        p1 = {"type": str(r.get("p1_type") if pd.notna(r.get("p1_type")) else default_meta.get("p1_type", "Quenching")),
              "temp": _safe_float(r.get("p1_temp"), default_meta.get("p1_temp", 930)),
              "time": _safe_float(r.get("p1_time_min"), default_meta.get("p1_time_min", 360)),
              "cooling": str(r.get("p1_cooling") if pd.notna(r.get("p1_cooling")) else default_meta.get("p1_cooling", "수냉(WQ)"))}
        p2 = {"type": str(r.get("p2_type") if pd.notna(r.get("p2_type")) else default_meta.get("p2_type", "Tempering")),
              "temp": _safe_float(r.get("p2_temp"), default_meta.get("p2_temp", 610)),
              "time": _safe_float(r.get("p2_time_min"), default_meta.get("p2_time_min", 240)),
              "cooling": str(r.get("p2_cooling") if pd.notna(r.get("p2_cooling")) else default_meta.get("p2_cooling", "공냉(AC)"))}
        p3 = {"type": str(r.get("p3_type") if pd.notna(r.get("p3_type")) else default_meta.get("p3_type", "S/R")),
              "temp": _safe_float(r.get("p3_temp"), default_meta.get("p3_temp", 625)),
              "time": _safe_float(r.get("p3_time_min"), default_meta.get("p3_time_min", 300)),
              "cooling": str(r.get("p3_cooling") if pd.notna(r.get("p3_cooling")) else default_meta.get("p3_cooling", "노냉(FC)"))}
        rows.append(build_measured_record(
            heat_no=str(r.get("heat_no") if pd.notna(r.get("heat_no")) else ""),
            material_grade=str(r.get("material_grade") if pd.notna(r.get("material_grade")) else default_meta.get("material_grade", "Imported")),
            product_name=str(r.get("product_name") if pd.notna(r.get("product_name")) else default_meta.get("product_name", "Imported Casting")),
            section_type=str(r.get("section_type") if pd.notna(r.get("section_type")) else default_meta.get("section_type", "Coupon")),
            comp=comp, p0=p0, p1=p1, p2=p2, p3=p3,
            thickness=_safe_float(r.get("thickness_mm"), default_meta.get("thickness_mm", 150)),
            coupon_thick=_safe_float(r.get("coupon_thickness_mm"), default_meta.get("coupon_thickness_mm", 50)),
            test_temp=_safe_float(r.get("test_temp_c"), default_meta.get("test_temp_c", -46)),
            actuals=actuals,
            note=str(r.get("note") if pd.notna(r.get("note")) else "자동 업로드 반영")
        ))
    return pd.DataFrame(rows)[_measured_columns()] if rows else pd.DataFrame(columns=_measured_columns())



# [PAGE CONFIG]
st.set_page_config(page_title="Sentinel-Alpha v6.6.0", layout="wide")

# [CSS CUSTOM STYLE]
st.markdown("""
    <style>
    .stMetric { background-color: #1e293b; padding: 15px; border-radius: 10px; border: 1px solid #334155; color: white; }
    .stMetric label { color: #94a3b8 !important; font-weight: bold; }
    .stMetric [data-testid="stMetricValue"] { color: #ffffff !important; font-weight: 800; }
    .main-title { color: #1e3a8a; font-size: 32px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">🛡️ Sentinel-Alpha v6.6.0: 전문가용 전공정 시뮬레이터</p>', unsafe_allow_html=True)

# [SIDEBAR - GLOBAL PARAMETERS]
with st.sidebar:
    st.header("⚙️ 기초 공정 변수 설정")
    input_thickness = st.number_input("주물 단면 두께 (mm)", min_value=10, max_value=2500, value=150, step=10)
    input_coupon_thick = st.number_input("시험편(Coupon) 두께 (mm)", min_value=10, max_value=2500, value=50, step=10)
    input_test_temp = st.selectbox("충격 시험 온도 (℃)", [20, 0, -20, -46, -60, -101], index=3)
    c_col1, c_col2 = st.columns(2)
    ceq_std = c_col1.selectbox("Ceq 규격", ["IIW (ASTM/ASME/EN)", "JIS", "CET (European)"])
    pcm_std = c_col2.selectbox("Pcm 규격", ["Pcm (Ito-Bessyo)", "None"])
    use_measured_calibration = st.checkbox("실측 데이터 기반 보정 적용", value=True)
    st.divider()
    st.info("Pusan National Univ. Metal Materials Lab\nQuality Management Specialist System")
    st.caption(f"Build Date: {datetime.now().strftime('%Y-%m-%d')}")

# [MAIN TABS INTERFACE]
tab_predict, tab_inverse, tab_measured = st.tabs(["🚀 정밀 물성 예측 시뮬레이션", "🔄 전문가용 역설계 엔진 (Inverse)", "📚 실측 데이터 누적/보정"])

# --- TAB 1: 물성 예측 ---
with tab_predict:
    st.header("1️⃣ 화학 성분 정밀 설계 (20 Elements Analysis)")
    
    # 20종 원소 입력을 위한 그리드 배치
    user_composition = {}
    col_row1 = st.columns(5); col_row2 = st.columns(5); col_row3 = st.columns(5); col_row4 = st.columns(5)
    
    element_list = ELEMENT_LIST
    
    for idx, element_name in enumerate(element_list):
        current_row = [col_row1, col_row2, col_row3, col_row4][idx // 5]
        default_val = 0.1850 if element_name == 'C' else 0.4500 if element_name == 'Si' else 1.4500 if element_name == 'Mn' else 0.0000
        user_composition[element_name] = current_row[idx % 5].number_input(
            f"{element_name} (%)", min_value=0.0, max_value=10.0, value=default_val, format="%.4f"
        )

    st.divider()
    st.header("2️⃣ 단계별 복합 열처리 시나리오 (1st ~ 3rd Stage)")
    
    c0, c1, c2, c3 = st.columns(4)
    
    with c0:
        st.subheader("📦 예비: 조직미세화")
        p0_type = st.selectbox("공정 종류", ["None", "Normalizing", "Homogenizing", "Annealing"], key="p0_type_select")
        p0_temp = st.number_input("열처리 온도 (℃)", 0, 1200, 950, step=10, key="p0_temp_input")
        st.write("가열 유지 시간")
        t_col1, t_col2 = st.columns(2)
        p0_h = t_col1.number_input("시간(hr)", 0, 100, 4, key="p0_h")
        p0_m = t_col2.number_input("분(min)", 0, 59, 0, key="p0_m")
        p0_time = p0_h * 60 + p0_m
        p0_cool = st.selectbox("냉각 방식", ["공냉(AC)", "노냉(FC)"], key="p0_cool_select")

    with c1:
        st.subheader("🔥 1차: 오스테나이트화")
        p1_type = st.selectbox("공정 종류", ["Quenching", "Normalizing", "Annealing"], key="p1_type_select")
        p1_temp = st.number_input("열처리 온도 (℃)", min_value=700, max_value=1200, value=1050, step=10, key="p1_temp_input")
        st.write("가열 유지 시간")
        t_col1, t_col2 = st.columns(2)
        p1_h = t_col1.number_input("시간(hr)", 0, 100, 6, key="p1_h")
        p1_m = t_col2.number_input("분(min)", 0, 59, 0, key="p1_m")
        p1_time = p1_h * 60 + p1_m
        p1_cool = st.selectbox("냉각 방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)"], key="p1_cool_select")
    
    with c2:
        st.subheader("🔥 2차: 뜨임/응력제거")
        p2_type = st.selectbox("공정 종류", ["None", "Tempering", "Normalizing", "Annealing"], index=1, key="p2_type_select")
        p2_temp = st.number_input("열처리 온도 (℃)", 0, 1200, 610, key="p2_temp_input")
        st.write("가열 유지 시간")
        t_col1, t_col2 = st.columns(2)
        p2_h = t_col1.number_input("시간(hr)", 0, 100, 4, key="p2_h")
        p2_m = t_col2.number_input("분(min)", 0, 59, 0, key="p2_m")
        p2_time = p2_h * 60 + p2_m
        p2_cool = st.selectbox("냉각 방식", ["공냉(AC)", "노냉(FC)", "수냉(WQ)"], key="p2_cool_select")
        
    with c3:
        st.subheader("❄️ 3차: 최종 PWHT")
        p3_type = st.selectbox("공정 종류", ["None", "S/R", "PWHT"], index=1, key="p3_type_select")
        p3_temp = st.number_input("열처리 온도 (℃)", 0, 850, 625, key="p3_temp_input")
        st.write("가열 유지 시간")
        t_col1, t_col2 = st.columns(2)
        p3_h = t_col1.number_input("시간(hr)", 0, 100, 5, key="p3_h")
        p3_m = t_col2.number_input("분(min)", 0, 59, 0, key="p3_m")
        p3_time = p3_h * 60 + p3_m
        p3_cool = st.selectbox("냉각 방식", ["노냉(FC)", "공냉(AC)"], key="p3_cool_select")

    if st.button("📊 정밀 물성 시뮬레이션 가동", use_container_width=True):
        ts_init = calc.calculate_1st_stage_physics(user_composition, {'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool}, input_thickness)
        ts_init_coupon = calc.calculate_1st_stage_physics(user_composition, {'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool}, input_coupon_thick)
        
        # 최종 물성 시뮬레이션 호출
        try:
            final_report = calc.run_simulation_v6(
                ts_1st=ts_init, 
                p2={'type':p2_type, 'temp':p2_temp, 'time':p2_time, 'cooling':p2_cool},
                p3={'type':p3_type, 'temp':p3_temp, 'time':p3_time, 'cooling':p3_cool},
                test_temp=input_test_temp, 
                comp=user_composition,
                p1={'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool},
                thickness=input_thickness,
                ceq_standard=ceq_std,
                p0={'type':p0_type, 'temp':p0_temp, 'time':p0_time, 'cooling':p0_cool}
            )
            coupon_report = calc.run_simulation_v6(
                ts_1st=ts_init_coupon, 
                p2={'type':p2_type, 'temp':p2_temp, 'time':p2_time, 'cooling':p2_cool},
                p3={'type':p3_type, 'temp':p3_temp, 'time':p3_time, 'cooling':p3_cool},
                test_temp=input_test_temp, 
                comp=user_composition,
                p1={'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool},
                thickness=input_coupon_thick,
                ceq_standard=ceq_std,
                p0={'type':p0_type, 'temp':p0_temp, 'time':p0_time, 'cooling':p0_cool}
            )
            final_report_raw = final_report.copy()
            coupon_report_raw = coupon_report.copy()
            final_report, calibration_info = apply_empirical_calibration(final_report, user_composition, input_thickness, use_measured_calibration)
            coupon_report, coupon_calibration_info = apply_empirical_calibration(coupon_report, user_composition, input_coupon_thick, use_measured_calibration)
        except TypeError as e:
            st.error(f"⚠️ 시뮬레이션 엔진 호출 오류 (TypeError): {e}")
            st.info("임시 해결책: 페이지를 새로고침(F5)하거나 관리자에게 문의하세요.")
            st.stop()
        except Exception as e:
            st.error(f"⚠️ 시뮬레이션 실행 중 예상치 못한 오류 발생: {e}")
            st.stop()
        
        st.success("### [Sentinel-Alpha 최종 기계적 물성 예측 리포트]")
        if use_measured_calibration:
            st.caption(f"📚 {calibration_info.get('message', '')}")
        st.info("💡 **질량 효과(Mass Effect)에 의한 제품 본체와 시험편의 물성 차이 비교**")
        
        rep_col1, rep_col2 = st.columns(2)
        with rep_col1:
            st.subheader(f"🔹 시험편(Coupon) 기준 ({input_coupon_thick}mm)")
            st.metric("항복강도 (YS)", f"{coupon_report['ys']} MPa")
            st.metric("인장강도 (TS)", f"{coupon_report['ts']} MPa")
            st.metric("연신율 (EL)", f"{coupon_report['el']} %")
            st.metric("단면수축률 (RA)", f"{coupon_report['ra']} %")
            st.metric("충격치 (CVN)", f"{coupon_report['cvn']} J")
            st.metric("브리넬 경도 (HB)", f"{coupon_report['hb']} HB")

        with rep_col2:
            st.subheader(f"🔸 제품 본체(Core) 기준 ({input_thickness}mm)")
            st.metric("항복강도 (YS)", f"{final_report['ys']} MPa")
            st.metric("인장강도 (TS)", f"{final_report['ts']} MPa")
            st.metric("연신율 (EL)", f"{final_report['el']} %")
            st.metric("단면수축률 (RA)", f"{final_report['ra']} %")
            st.metric("충격치 (CVN)", f"{final_report['cvn']} J")
            st.metric("브리넬 경도 (HB)", f"{final_report['hb']} HB")

        st.divider()
        st.subheader("🧪 탄소당량 분석 (Carbon Equivalent Analysis)")
        ceq_all = final_report['ceq_all']
        
        # 선택된 규격에 따른 표시 로직
        res_cols = st.columns(2)
        
        # Ceq 표시
        ceq_map = {"IIW (ASTM/ASME/EN)": ("Ceq (IIW)", "ceq_iiw"), "JIS": ("Ceq (JIS)", "ceq_jis"), "CET (European)": ("CET", "cet")}
        ceq_label, ceq_key = ceq_map.get(ceq_std)
        res_cols[0].metric(ceq_label, f"{ceq_all[ceq_key]}")
        
        # Pcm 표시
        if pcm_std != "None":
            res_cols[1].metric("Pcm (Ito-Bessyo)", f"{ceq_all['pcm']}")
        else:
            res_cols[1].info("Pcm 표시 안 함")
        
        st.divider()
        st.subheader("🔬 미세조직 및 야금학적 특성")

        with st.expander("🔬 예상 미세조직 (Estimated Microstructure)", expanded=True):
            c_left, c_right = st.columns([1, 2])
            c_left.info(f"**주요 조직명:**\n\n### {final_report['micro_name']}")
            c_right.warning(f"**조직 구조 및 특징:**\n\n{final_report['micro_desc']}")
        
        if IS_PLOTLY_AVAILABLE:
            radar_fig = go.Figure(data=go.Scatterpolar(
                r=[final_report['ts']/10, final_report['el']*2, final_report['ra']*1.5, final_report['hb']/2, final_report['cvn']],
                theta=['TS','EL','RA','HB','CVN'], fill='toself', name='Predicted Property'
            ))
            st.plotly_chart(radar_fig, use_container_width=True)

        # [추가] 두께별 물성 민감도 분석 차트
        st.divider()
        st.subheader("🔍 두께별 물성 민감도 분석 (Mass Effect Analysis)")
        st.write("현재 성분 및 열처리 조건에서 두께 변화에 따른 강도 저하 추이를 시뮬레이션합니다.")
        
        thickness_range = np.linspace(10, max(1000, input_thickness*2), 60)
        sim_results = []
        p0_current = {'type':p0_type, 'temp':p0_temp, 'time':p0_time, 'cooling':p0_cool}
        p1_current = {'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool}
        p2_current = {'type':p2_type, 'temp':p2_temp, 'time':p2_time, 'cooling':p2_cool}
        p3_current = {'type':p3_type, 'temp':p3_temp, 'time':p3_time, 'cooling':p3_cool}
        for t in thickness_range:
            ts_1st = calc.calculate_1st_stage_physics(user_composition, p1_current, t)
            rep = calc.get_final_expert_simulation(ts_1st, p2_current, p3_current, input_test_temp, user_composition, p1=p1_current, thickness=t, ceq_standard=ceq_std, p0=p0_current)
            rep, _ = apply_empirical_calibration(rep, user_composition, t, use_measured_calibration)
            sim_results.append({'Thickness': round(float(t), 1), 'YS': rep['ys'], 'TS': rep['ts'], 'EL': rep['el'], 'RA': rep['ra'], 'CVN': rep['cvn'], 'HB': rep['hb']})

        sim_df = pd.DataFrame(sim_results)

        def pred_mass_point(section_thickness, label):
            ts_1st = calc.calculate_1st_stage_physics(user_composition, p1_current, section_thickness)
            rep = calc.get_final_expert_simulation(ts_1st, p2_current, p3_current, input_test_temp, user_composition, p1=p1_current, thickness=section_thickness, ceq_standard=ceq_std, p0=p0_current)
            rep, _ = apply_empirical_calibration(rep, user_composition, section_thickness, use_measured_calibration)
            return {'구분': label, '두께(mm)': section_thickness, 'YS(MPa)': rep['ys'], 'TS(MPa)': rep['ts'], 'EL(%)': rep['el'], 'RA(%)': rep['ra'], 'CVN(J)': rep['cvn'], 'HB': rep['hb']}

        pred_mass_summary_df = pd.DataFrame([
            pred_mass_point(input_coupon_thick, '시험편 Coupon'),
            pred_mass_point(input_thickness, '제품 본체 Core'),
            pred_mass_point(max(1000, input_thickness*2), '검토 최대 두께')
        ])
        st.write("#### 📌 두께 기준별 예측 물성 요약")
        st.dataframe(pred_mass_summary_df, use_container_width=True, hide_index=True)

        coupon_row = pred_mass_summary_df.iloc[0]
        core_row = pred_mass_summary_df.iloc[1]
        delta_cols = st.columns(6)
        delta_cols[0].metric("YS 변화", f"{core_row['YS(MPa)'] - coupon_row['YS(MPa)']:.1f} MPa")
        delta_cols[1].metric("TS 변화", f"{core_row['TS(MPa)'] - coupon_row['TS(MPa)']:.1f} MPa")
        delta_cols[2].metric("EL 변화", f"{core_row['EL(%)'] - coupon_row['EL(%)']:.1f} %")
        delta_cols[3].metric("RA 변화", f"{core_row['RA(%)'] - coupon_row['RA(%)']:.1f} %")
        delta_cols[4].metric("CVN 변화", f"{core_row['CVN(J)'] - coupon_row['CVN(J)']:.1f} J")
        delta_cols[5].metric("HB 변화", f"{core_row['HB'] - coupon_row['HB']:.1f} HB")

        if IS_PLOTLY_AVAILABLE:
            strength_tab, ductility_tab, toughness_tab = st.tabs(["강도/경도", "연성", "충격치"])
            with strength_tab:
                fig_sens = go.Figure()
                fig_sens.add_trace(go.Scatter(x=sim_df['Thickness'], y=sim_df['TS'], name='인장강도 (TS)', line=dict(color='#ef4444', width=3)))
                fig_sens.add_trace(go.Scatter(x=sim_df['Thickness'], y=sim_df['YS'], name='항복강도 (YS)', line=dict(color='#3b82f6', width=3, dash='dash')))
                fig_sens.add_trace(go.Scatter(x=sim_df['Thickness'], y=sim_df['HB'], name='브리넬 경도 (HB)', yaxis='y2', line=dict(color='#f59e0b', width=3, dash='dot')))
                fig_sens.update_layout(title="두께 증가에 따른 강도/경도 변화", xaxis_title="두께 (mm)", yaxis_title="강도 (MPa)", yaxis2=dict(title="경도 (HB)", overlaying='y', side='right'), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                fig_sens.add_vline(x=input_thickness, line_dash="dot", line_color="green", annotation_text=f"현재 설정: {input_thickness}mm")
                fig_sens.add_vline(x=input_coupon_thick, line_dash="dash", line_color="gray", annotation_text=f"Coupon: {input_coupon_thick}mm")
                st.plotly_chart(fig_sens, use_container_width=True)
            with ductility_tab:
                fig_duct = go.Figure()
                fig_duct.add_trace(go.Scatter(x=sim_df['Thickness'], y=sim_df['EL'], name='연신율 (EL)', line=dict(width=3)))
                fig_duct.add_trace(go.Scatter(x=sim_df['Thickness'], y=sim_df['RA'], name='단면수축률 (RA)', line=dict(width=3, dash='dash')))
                fig_duct.update_layout(title="두께별 연성 변화", xaxis_title="두께 (mm)", yaxis_title="연성 (%)", hovermode="x unified")
                fig_duct.add_vline(x=input_thickness, line_dash="dot", line_color="green", annotation_text=f"현재 설정: {input_thickness}mm")
                st.plotly_chart(fig_duct, use_container_width=True)
            with toughness_tab:
                fig_cvn = go.Figure()
                fig_cvn.add_trace(go.Scatter(x=sim_df['Thickness'], y=sim_df['CVN'], name='충격치 (CVN)', line=dict(width=3)))
                fig_cvn.update_layout(title="두께별 CVN 민감도", xaxis_title="두께 (mm)", yaxis_title="CVN (J)", hovermode="x unified")
                fig_cvn.add_vline(x=input_thickness, line_dash="dot", line_color="green", annotation_text=f"현재 설정: {input_thickness}mm")
                st.plotly_chart(fig_cvn, use_container_width=True)
        else:
            st.line_chart(sim_df.set_index('Thickness')[['TS', 'YS', 'HB', 'CVN', 'EL', 'RA']])

        st.info("💡 **전문가 팁**: 그래프의 기울기가 급격히 변하는 지점이 해당 합금의 유효 경화 깊이 한계입니다. 대형재의 경우 Mo, Cr 함량을 높여 그래프를 완만하게 만들어야 합니다.")

# --- TAB 2: 역설계 엔진 ---
with tab_inverse:
    st.header("🔄 전문가용 역설계 엔진 (Inverse Engineering)")
    st.write("목표하는 기계적 물성을 입력하면, Sentinel-Alpha가 최적의 합금 성분과 열처리 조건을 역으로 제안합니다.")
    
    st.subheader("🎯 목표 기계적 성질 및 설계 조건 (Targets & Specs)")
    ir_col1, ir_col2 = st.columns(2)
    with ir_col1:
        target_ys = st.number_input("목표 항복강도 (MPa)", 100, 1500, 485)
        target_ts = st.number_input("목표 인장강도 (MPa)", 200, 2000, 625)
        target_el = st.number_input("목표 연신율 (%)", 5, 80, 22)
    with ir_col2:
        target_ra = st.number_input("목표 단면수축률 (%)", 10, 80, 45)
        target_hb = st.number_input("목표 경도 (HB)", 100, 500, 210)
        target_cvn = st.number_input("목표 충격치 (J)", 10, 300, 65)
    
    st.divider()
    target_thick = st.number_input("설계 대상 소재 두께 (mm)", 10, 2500, input_thickness)
    st.info("※ 입력된 두께에 따라 질량 효과를 고려한 합금 성분 및 **1차 오스테나이트화 온도**가 자동으로 예측됩니다.")
        
    if st.button("🔍 최적 설계 시나리오 도출", use_container_width=True):
        inverse_results = calc.run_inverse_v6(targets={
            'ys': target_ys, 'ts': target_ts, 'cvn': target_cvn,
            'el': target_el, 'ra': target_ra, 'hb': target_hb,
            'test_temp': input_test_temp, 
            'thick': target_thick,
            'coupon_thick': input_coupon_thick,
            'ceq_standard': ceq_std
        })
        
        st.success("### [Sentinel-Alpha 추천 최적 설계 사양]")
        
        # 전문가 분석 코멘트 추가
        if inverse_results.get('comments'):
            with st.expander("🧐 전문가 분석 의견 (Technical Insights)", expanded=True):
                for comment in inverse_results['comments']:
                    st.write(f"- {comment}")
                
                info_text = f"**{inverse_results['ceq_label']}:** {inverse_results['ceq_val']} (규격: {ceq_std})"
                if pcm_std != "None" and 'ceq_all' in inverse_results:
                    info_text += f" &nbsp;|&nbsp; **Pcm (Ito-Bessyo):** {inverse_results['ceq_all']['pcm']}"
                st.info(info_text)

        st.divider()
        st.subheader("🔬 예측 미세조직 및 야금학적 구조")
        with st.expander("🔬 역설계 조건부 예상 미세조직 (Estimated Microstructure)", expanded=True):
            c_left, c_right = st.columns([1, 2])
            c_left.info(f"**주요 조직명:**\n\n### {inverse_results.get('micro_name', 'N/A')}")
            c_right.warning(f"**조직 구조 및 특징:**\n\n{inverse_results.get('micro_desc', 'N/A')}")

        st.divider()
        st.write("#### 1️⃣ 추천 성분 배합비 (Chemical Composition)")
        st.info("💡 목표 물성을 시험편에 맞출 때와 제품 본체에 맞출 때 필요한 탄소(C) 배합량이 어떻게 다른지 비교합니다.")
        
        def styled_alloy_df(alloy_dict):
            df = pd.DataFrame([alloy_dict])
            return df.style.format({"C": "{:.2f}"})
        
        st.write(f"🔸 **제품 본체(Core) 기준 최소 배합비**")
        st.dataframe(styled_alloy_df(inverse_results['alloy_prod']), use_container_width=True)
        
        st.write(f"🔹 **시험편(Coupon) 기준 최소 배합비**")
        st.dataframe(styled_alloy_df(inverse_results['alloy_coupon']), use_container_width=True)
        
        st.write("#### 2️⃣ 추천 열처리 공정 스케줄")
        p_list = []
        if inverse_results.get('p0') and inverse_results['p0']['mode'] != "None":
            p_list.append(("예비", inverse_results['p0']))
        p_list.extend([("1차", inverse_results['p1']), ("2차", inverse_results['p2']), ("3차", inverse_results['p3'])])
        
        for idx_name, p in p_list:
            h_val = int(p['time']) // 60
            m_val = int(p['time']) % 60
            time_str = f"{h_val}시간 {m_val}분" if h_val > 0 else f"{m_val}분"
            st.info(f"**{idx_name} 공정 ({p['mode']})**: {p['temp']}℃ / {time_str} / 냉각: :blue[{p['cool']}]")

        st.divider()
        st.subheader("🔬 역설계 물성 교차 검증 (Cross-Validation)")
        st.info("💡 목표 물성을 시험편에 맞춰 도출된 합금 및 공정 조건이, 실제 제품 본체 내부에서는 어떻게 달라지는지 비교합니다.")
        
        c_rep = inverse_results['coupon_rep']
        p_rep = inverse_results['prod_rep']
        
        vr_col1, vr_col2 = st.columns(2)
        with vr_col1:
            st.subheader(f"🔹 시험편 예상 (목표치 매칭) ({input_coupon_thick}mm)")
            st.metric("항복강도 (YS)", f"{c_rep['ys']} MPa")
            st.metric("인장강도 (TS)", f"{c_rep['ts']} MPa")
            st.metric("연신율 (EL)", f"{c_rep['el']} %")
            st.metric("단면수축률 (RA)", f"{c_rep['ra']} %")
            st.metric("충격치 (CVN)", f"{c_rep['cvn']} J")
            st.metric("브리넬 경도 (HB)", f"{c_rep['hb']} HB")

        with vr_col2:
            st.subheader(f"🔸 제품 본체 코어 예상 ({target_thick}mm)")
            st.metric("항복강도 (YS)", f"{p_rep['ys']} MPa")
            st.metric("인장강도 (TS)", f"{p_rep['ts']} MPa")
            st.metric("연신율 (EL)", f"{p_rep['el']} %")
            st.metric("단면수축률 (RA)", f"{p_rep['ra']} %")
            st.metric("충격치 (CVN)", f"{p_rep['cvn']} J")
            st.metric("브리넬 경도 (HB)", f"{p_rep['hb']} HB")

        st.divider()
        st.subheader("🔍 역설계 결과: 두께별 물성 민감도 분석 (Mass Effect Analysis)")
        st.write("추천된 합금 성분 및 열처리 스케줄이 실제 제품 두께에 따라 강도·연성·충격치·경도에 미치는 영향을 시뮬레이션합니다.")
        st.caption("※ Mass Effect는 단면 두께 증가에 따른 중심부 냉각속도 저하 및 경화능 한계를 반영한 민감도 분석입니다.")
        
        thickness_range = np.linspace(10, max(1000, target_thick*2), 60)
        inv_sim_results = []
        inv_alloy = inverse_results['alloy']
        inv_p0 = {'type': inverse_results['p0']['mode'], 'temp': inverse_results['p0']['temp'], 'time': inverse_results['p0']['time'], 'cooling': inverse_results['p0']['cool']} if inverse_results.get('p0') else None
        inv_p1 = {'type': inverse_results['p1']['mode'], 'temp': inverse_results['p1']['temp'], 'time': inverse_results['p1']['time'], 'cooling': inverse_results['p1']['cool']}
        inv_p2 = {'type': inverse_results['p2']['mode'], 'temp': inverse_results['p2']['temp'], 'time': inverse_results['p2']['time'], 'cooling': inverse_results['p2']['cool']}
        inv_p3 = {'type': inverse_results['p3']['mode'], 'temp': inverse_results['p3']['temp'], 'time': inverse_results['p3']['time'], 'cooling': inverse_results['p3']['cool']}
        
        for t in thickness_range:
            ts_1st = calc.calculate_1st_stage_physics(inv_alloy, inv_p1, t)
            rep = calc.get_final_expert_simulation(ts_1st, inv_p2, inv_p3, input_test_temp, inv_alloy, p1=inv_p1, thickness=t, p0=inv_p0, ceq_standard=ceq_std)
            inv_sim_results.append({
                'Thickness': round(float(t), 1),
                'YS': rep['ys'], 'TS': rep['ts'], 'EL': rep['el'], 'RA': rep['ra'], 'CVN': rep['cvn'], 'HB': rep['hb']
            })
        
        inv_sim_df = pd.DataFrame(inv_sim_results)

        # Coupon / product / maximum thickness comparison table
        def mass_point(section_thickness, label):
            ts_1st = calc.calculate_1st_stage_physics(inv_alloy, inv_p1, section_thickness)
            rep = calc.get_final_expert_simulation(ts_1st, inv_p2, inv_p3, input_test_temp, inv_alloy, p1=inv_p1, thickness=section_thickness, p0=inv_p0, ceq_standard=ceq_std)
            return {
                '구분': label, '두께(mm)': section_thickness,
                'YS(MPa)': rep['ys'], 'TS(MPa)': rep['ts'], 'EL(%)': rep['el'],
                'RA(%)': rep['ra'], 'CVN(J)': rep['cvn'], 'HB': rep['hb']
            }

        mass_summary_df = pd.DataFrame([
            mass_point(input_coupon_thick, '시험편 Coupon'),
            mass_point(target_thick, '제품 본체 Core'),
            mass_point(max(1000, target_thick*2), '검토 최대 두께')
        ])
        st.write("#### 📌 두께 기준별 예측 물성 요약")
        st.dataframe(mass_summary_df, use_container_width=True, hide_index=True)

        # Sensitivity loss/gain from coupon to product core
        coupon_row = mass_summary_df.iloc[0]
        core_row = mass_summary_df.iloc[1]
        loss_cols = st.columns(4)
        loss_cols[0].metric("TS 변화", f"{core_row['TS(MPa)'] - coupon_row['TS(MPa)']:.1f} MPa")
        loss_cols[1].metric("YS 변화", f"{core_row['YS(MPa)'] - coupon_row['YS(MPa)']:.1f} MPa")
        loss_cols[2].metric("CVN 변화", f"{core_row['CVN(J)'] - coupon_row['CVN(J)']:.1f} J")
        loss_cols[3].metric("HB 변화", f"{core_row['HB'] - coupon_row['HB']:.1f} HB")
        
        if IS_PLOTLY_AVAILABLE:
            strength_tab, ductility_tab, toughness_tab = st.tabs(["강도/경도", "연성", "충격치"])
            with strength_tab:
                fig_inv_sens = go.Figure()
                fig_inv_sens.add_trace(go.Scatter(x=inv_sim_df['Thickness'], y=inv_sim_df['TS'], name='인장강도 (TS)', line=dict(color='#ef4444', width=3)))
                fig_inv_sens.add_trace(go.Scatter(x=inv_sim_df['Thickness'], y=inv_sim_df['YS'], name='항복강도 (YS)', line=dict(color='#3b82f6', width=3, dash='dash')))
                fig_inv_sens.add_trace(go.Scatter(x=inv_sim_df['Thickness'], y=inv_sim_df['HB'], name='브리넬 경도 (HB)', yaxis='y2', line=dict(color='#f59e0b', width=3, dash='dot')))
                fig_inv_sens.update_layout(
                    title="역설계 도출 조건 적용 시 두께별 강도 및 경도 변화",
                    xaxis_title="두께 (mm)", yaxis_title="강도 (MPa)",
                    yaxis2=dict(title="경도 (HB)", overlaying='y', side='right'),
                    hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                fig_inv_sens.add_vline(x=target_thick, line_dash="dot", line_color="green", annotation_text=f"목표 두께: {target_thick}mm")
                fig_inv_sens.add_vline(x=input_coupon_thick, line_dash="dash", line_color="gray", annotation_text=f"Coupon: {input_coupon_thick}mm")
                st.plotly_chart(fig_inv_sens, use_container_width=True)
            with ductility_tab:
                fig_duct = go.Figure()
                fig_duct.add_trace(go.Scatter(x=inv_sim_df['Thickness'], y=inv_sim_df['EL'], name='연신율 (EL)', line=dict(width=3)))
                fig_duct.add_trace(go.Scatter(x=inv_sim_df['Thickness'], y=inv_sim_df['RA'], name='단면수축률 (RA)', line=dict(width=3, dash='dash')))
                fig_duct.update_layout(title="두께별 연성 변화", xaxis_title="두께 (mm)", yaxis_title="연성 (%)", hovermode="x unified")
                fig_duct.add_vline(x=target_thick, line_dash="dot", line_color="green", annotation_text=f"목표 두께: {target_thick}mm")
                st.plotly_chart(fig_duct, use_container_width=True)
            with toughness_tab:
                fig_cvn = go.Figure()
                fig_cvn.add_trace(go.Scatter(x=inv_sim_df['Thickness'], y=inv_sim_df['CVN'], name='충격치 (CVN)', line=dict(width=3)))
                fig_cvn.add_hline(y=target_cvn, line_dash="dash", line_color="red", annotation_text=f"목표 CVN: {target_cvn}J")
                fig_cvn.add_vline(x=target_thick, line_dash="dot", line_color="green", annotation_text=f"목표 두께: {target_thick}mm")
                fig_cvn.update_layout(title="두께별 CVN 민감도", xaxis_title="두께 (mm)", yaxis_title="CVN (J)", hovermode="x unified")
                st.plotly_chart(fig_cvn, use_container_width=True)
        else:
            st.line_chart(inv_sim_df.set_index('Thickness')[['TS', 'YS', 'HB', 'CVN', 'EL', 'RA']])

        st.warning("⚠️ 두께 증가 시 TS/YS/HB 저하가 크거나 CVN이 급격히 낮아지는 구간은 경화능 부족 또는 중심부 냉각속도 부족 가능성이 큰 영역입니다. 실제 양산 전에는 제품부착 시험편 또는 대표 단면 시험으로 보정이 필요합니다.")


# --- TAB 3: 실측 데이터 누적/보정 ---
with tab_measured:
    st.header("📚 실측 데이터 누적 및 예측 보정 엔진")
    st.write("실제 Heat/MTR/기계시험 결과를 누적하면 예측값과 실측값의 잔차를 계산하여 이후 예측 시뮬레이션에 자동 보정값으로 반영합니다.")

    db_df = load_measured_db()
    m1, m2, m3 = st.columns(3)
    m1.metric("누적 실측 데이터", f"{len(db_df)} 건")
    m2.metric("보정 가능 데이터", f"{len(db_df.dropna(subset=['residual_ts','residual_ys'], how='all')) if not db_df.empty else 0} 건")
    if not db_df.empty and 'timestamp' in db_df and len(db_df['timestamp'].dropna()) > 0:
        m3.metric("최종 입력", str(db_df['timestamp'].dropna().iloc[-1]))
    else:
        m3.metric("최종 입력", "-")

    st.divider()
    st.subheader("1️⃣ 실측 데이터 수동 입력")
    st.caption("MTR 또는 시험성적서의 Heat 성분/열처리/기계적 물성값을 누적하는 DB입니다. 0으로 둔 물성은 미입력값으로 처리됩니다.")
    meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
    heat_no = meta_col1.text_input("Heat No.", value="")
    material_grade = meta_col2.text_input("재질/규격", value="ASTM A352 LCC")
    product_name = meta_col3.text_input("제품명", value="Casting")
    section_type = meta_col4.selectbox("시험 위치", ["Coupon", "Product Attached", "Core", "Surface", "Other"])

    st.write("#### 화학성분 입력")
    comp_input = {}
    comp_cols = st.columns(5)
    default_comp = {'C':0.185, 'Si':0.45, 'Mn':1.45, 'P':0.010, 'S':0.005, 'Ni':0.35, 'Cr':0.25, 'Mo':0.08}
    for idx, e in enumerate(ELEMENT_LIST):
        comp_input[e] = comp_cols[idx % 5].number_input(f"실측 {e}(%)", min_value=0.0, max_value=10.0, value=float(default_comp.get(e, 0.0)), format="%.4f", key=f"actual_comp_{e}")

    st.write("#### 열처리 조건")
    hp0, hp1, hp2, hp3 = st.columns(4)
    with hp0:
        a_p0_type = st.selectbox("예비 공정", ["None", "Normalizing", "Homogenizing", "Annealing"], key="actual_p0_type")
        a_p0_temp = st.number_input("예비 온도(℃)", 0, 1200, 950, key="actual_p0_temp")
        a_p0_time = st.number_input("예비 시간(min)", 0, 10000, 240, key="actual_p0_time")
        a_p0_cool = st.selectbox("예비 냉각", ["공냉(AC)", "노냉(FC)"], key="actual_p0_cool")
    with hp1:
        a_p1_type = st.selectbox("1차 공정", ["Quenching", "Normalizing", "Annealing"], key="actual_p1_type")
        a_p1_temp = st.number_input("1차 온도(℃)", 700, 1200, 930, key="actual_p1_temp")
        a_p1_time = st.number_input("1차 시간(min)", 0, 10000, 360, key="actual_p1_time")
        a_p1_cool = st.selectbox("1차 냉각", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)"], key="actual_p1_cool")
    with hp2:
        a_p2_type = st.selectbox("2차 공정", ["None", "Tempering", "Normalizing", "Annealing"], index=1, key="actual_p2_type")
        a_p2_temp = st.number_input("2차 온도(℃)", 0, 1200, 610, key="actual_p2_temp")
        a_p2_time = st.number_input("2차 시간(min)", 0, 10000, 240, key="actual_p2_time")
        a_p2_cool = st.selectbox("2차 냉각", ["공냉(AC)", "노냉(FC)", "수냉(WQ)"], key="actual_p2_cool")
    with hp3:
        a_p3_type = st.selectbox("3차 공정", ["None", "S/R", "PWHT"], index=1, key="actual_p3_type")
        a_p3_temp = st.number_input("3차 온도(℃)", 0, 850, 625, key="actual_p3_temp")
        a_p3_time = st.number_input("3차 시간(min)", 0, 10000, 300, key="actual_p3_time")
        a_p3_cool = st.selectbox("3차 냉각", ["노냉(FC)", "공냉(AC)"], key="actual_p3_cool")

    st.write("#### 실측 기계적 물성")
    ap1, ap2, ap3, ap4 = st.columns(4)
    actual_thickness = ap1.number_input("실측 위치 두께(mm)", 10, 2500, input_thickness, key="actual_thickness")
    actual_coupon_thick = ap2.number_input("Coupon 두께(mm)", 10, 2500, input_coupon_thick, key="actual_coupon_thick")
    actual_test_temp = ap3.number_input("충격 시험 온도(℃)", -196, 200, input_test_temp, key="actual_test_temp")
    note = ap4.text_input("비고", value="")
    prop_cols = st.columns(6)
    actuals = {
        'ys': prop_cols[0].number_input("실측 YS(MPa)", 0.0, 2000.0, 0.0, key="actual_ys"),
        'ts': prop_cols[1].number_input("실측 TS(MPa)", 0.0, 2500.0, 0.0, key="actual_ts"),
        'el': prop_cols[2].number_input("실측 EL(%)", 0.0, 100.0, 0.0, key="actual_el"),
        'ra': prop_cols[3].number_input("실측 RA(%)", 0.0, 100.0, 0.0, key="actual_ra"),
        'cvn': prop_cols[4].number_input("실측 CVN(J)", 0.0, 500.0, 0.0, key="actual_cvn"),
        'hb': prop_cols[5].number_input("실측 HB", 0.0, 700.0, 0.0, key="actual_hb"),
    }
    actuals = {k: (np.nan if v == 0 else v) for k, v in actuals.items()}

    if st.button("➕ 실측 데이터 저장 및 보정 DB 반영", use_container_width=True):
        p0_m = {'type': a_p0_type, 'temp': a_p0_temp, 'time': a_p0_time, 'cooling': a_p0_cool}
        p1_m = {'type': a_p1_type, 'temp': a_p1_temp, 'time': a_p1_time, 'cooling': a_p1_cool}
        p2_m = {'type': a_p2_type, 'temp': a_p2_temp, 'time': a_p2_time, 'cooling': a_p2_cool}
        p3_m = {'type': a_p3_type, 'temp': a_p3_temp, 'time': a_p3_time, 'cooling': a_p3_cool}
        row = build_measured_record(heat_no, material_grade, product_name, section_type, comp_input, p0_m, p1_m, p2_m, p3_m, actual_thickness, actual_coupon_thick, actual_test_temp, actuals, note)
        db_df = pd.concat([load_measured_db(), pd.DataFrame([row])], ignore_index=True)
        save_measured_db(db_df)
        st.success("실측 데이터가 저장되었고, 다음 예측부터 보정 후보 데이터로 사용됩니다.")

    st.divider()
    st.subheader("2️⃣ Excel / PDF / CSV 자동 업로드 및 누적 데이터 관리")
    st.caption("MTR, 기계시험 성적서, Heat 성분표를 Excel 또는 PDF로 업로드하면 주요 성분/열처리/실측 물성을 자동 추출합니다. PDF는 양식 편차가 크므로 미리보기 확인 후 DB에 반영하세요.")

    up_col1, up_col2 = st.columns([2, 1])
    uploaded_file = up_col1.file_uploader("실측 성적서 업로드", type=["xlsx", "xls", "csv", "pdf"], help="권장: Excel은 첫 행에 C, Si, Mn, YS, TS, EL, RA, CVN, HB 등 컬럼명을 넣으면 가장 정확합니다.")
    with up_col2:
        st.write("자동 인식 가능 항목")
        st.caption("Heat No. / 재질 / 두께 / C~Zr 20원소 / 열처리 조건 / YS·TS·EL·RA·CVN·HB")

    if uploaded_file is not None:
        try:
            file_name = uploaded_file.name.lower()
            if file_name.endswith(".pdf"):
                parsed_df = parse_pdf_certificate(uploaded_file)
            else:
                parsed_df = parse_excel_or_csv(uploaded_file)

            if parsed_df.empty:
                st.warning("자동 추출 가능한 행을 찾지 못했습니다. Excel은 컬럼명을 확인하고, PDF는 텍스트 선택이 가능한 성적서인지 확인해 주세요.")
            else:
                default_meta = {
                    "material_grade": material_grade, "product_name": product_name, "section_type": section_type,
                    "thickness_mm": actual_thickness, "coupon_thickness_mm": actual_coupon_thick, "test_temp_c": actual_test_temp,
                    "p0_type": a_p0_type, "p0_temp": a_p0_temp, "p0_time_min": a_p0_time, "p0_cooling": a_p0_cool,
                    "p1_type": a_p1_type, "p1_temp": a_p1_temp, "p1_time_min": a_p1_time, "p1_cooling": a_p1_cool,
                    "p2_type": a_p2_type, "p2_temp": a_p2_temp, "p2_time_min": a_p2_time, "p2_cooling": a_p2_cool,
                    "p3_type": a_p3_type, "p3_temp": a_p3_temp, "p3_time_min": a_p3_time, "p3_cooling": a_p3_cool,
                }
                completed_df = _complete_import_rows(parsed_df, default_meta=default_meta)
                st.success(f"자동 추출 완료: 후보 {len(parsed_df)}행 / 보정 DB 반영 가능 {len(completed_df)}행")
                st.write("#### 추출 미리보기")
                preview_cols = ["heat_no", "material_grade", "product_name", "thickness_mm", "comp_C", "comp_Si", "comp_Mn", "actual_ys", "actual_ts", "actual_el", "actual_ra", "actual_cvn", "actual_hb", "note"]
                st.dataframe(completed_df[[c for c in preview_cols if c in completed_df.columns]], use_container_width=True, hide_index=True)

                if st.button("✅ 미리보기 데이터 누적 DB 반영", use_container_width=True):
                    current = load_measured_db()
                    merged = pd.concat([current, completed_df], ignore_index=True)
                    save_measured_db(merged)
                    st.success(f"업로드 파일에서 추출한 {len(completed_df)}건을 누적 DB에 반영했습니다. 다음 예측부터 보정 데이터로 사용됩니다.")
        except Exception as e:
            st.error(f"파일 자동 업로드/추출 오류: {e}")

    template_cols = ["heat_no", "material_grade", "product_name", "section_type", "thickness_mm", "coupon_thickness_mm", "test_temp_c"] + [f"comp_{e}" for e in ELEMENT_LIST] + [f"actual_{k}" for k in PROP_KEYS] + ["p1_temp", "p1_time_min", "p1_cooling", "p2_temp", "p2_time_min", "p3_temp", "p3_time_min", "note"]
    st.download_button("⬇️ Excel/CSV 업로드 템플릿 다운로드", pd.DataFrame(columns=template_cols).to_csv(index=False, encoding="utf-8-sig"), file_name="sentinel_measured_upload_template.csv", mime="text/csv", use_container_width=True)

    db_df = load_measured_db()
    if not db_df.empty:
        st.dataframe(db_df.tail(100), use_container_width=True, hide_index=True)
        st.download_button("⬇️ 누적 실측 DB 다운로드", db_df.to_csv(index=False, encoding="utf-8-sig"), file_name="measured_property_database.csv", mime="text/csv", use_container_width=True)
        if st.button("🧹 누적 DB 초기화", type="secondary"):
            save_measured_db(pd.DataFrame(columns=_measured_columns()))
            st.warning("누적 실측 DB를 초기화했습니다. 페이지를 새로고침하면 반영됩니다.")
    else:
        st.info("아직 누적된 실측 데이터가 없습니다.")

    st.divider()
    st.subheader("3️⃣ 자동 추출 및 보정 방식 설명")
    st.write("- 수동 입력 또는 Excel/PDF/CSV 업로드 시 현재 엔진 예측값과 실측값의 차이, 즉 `actual - predicted` 잔차를 함께 저장합니다.")
    st.write("- 예측 시뮬레이션에서는 두께, Ceq, Pcm이 유사한 누적 데이터에 더 높은 가중치를 부여하여 YS/TS/EL/RA/CVN/HB를 보정합니다.")
    st.write("- PDF 자동 추출은 성적서 양식에 따라 인식률 차이가 있으므로, 반드시 미리보기 값 확인 후 DB에 반영하는 구조로 설계했습니다.")
    st.warning("주의: 데이터가 적을 때는 보정 신뢰도가 낮습니다. 최소 3건 이상부터 보정이 적용되며, 동일 재질·동일 열처리·유사 두께 데이터가 많을수록 정확도가 높아집니다.")
