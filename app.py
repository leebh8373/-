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

__version__ = "6.6.3" # OCR PDF/Image Import + Manual Thickness Override Patch

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


def _direct_extract_pdf_text(data):
    """텍스트 선택 가능한 PDF에서 일반 텍스트를 추출합니다."""
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page in pdf.pages:
                text += "\n" + (page.extract_text() or "")
    except Exception:
        text = ""
    if len(re.sub(r"\s+", "", text)) < 50:
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            for page in reader.pages:
                text += "\n" + (page.extract_text() or "")
        except Exception:
            pass
    return text


def _pdf_text_has_useful_values(text):
    """성분/물성 라벨이 충분히 있는지 판단하여 OCR 필요 여부를 결정합니다."""
    compact = re.sub(r"\s+", "", text or "").lower()
    if len(compact) < 250:
        return False
    labels = [
        "yield", "tensile", "elong", "impact", "charpy", "hardness", "brinell",
        "ys", "uts", "rp0.2", "hb", "hbw", "cvn", "항복", "인장", "연신", "충격", "경도",
    ]
    hits = sum(1 for x in labels if x.replace(" ", "") in compact)
    return hits >= 2


def _ocr_pdf_text(data, max_pages=6, zoom=2.7):
    """이미지/스캔 PDF를 페이지 이미지로 렌더링한 뒤 OCR로 텍스트를 추출합니다.
    - PyMuPDF(fitz)로 PDF 페이지를 이미지화
    - PIL 전처리: 회색조, 자동 대비, 확대
    - Tesseract OCR: 영문+한글 성적서 대응
    """
    ocr_text = ""
    try:
        import fitz  # PyMuPDF
        import pytesseract
        from PIL import Image, ImageOps, ImageFilter
        doc = fitz.open(stream=data, filetype="pdf")
        page_count = min(len(doc), max_pages)
        for page_idx in range(page_count):
            page = doc.load_page(page_idx)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img)
            # 성적서 표의 작은 숫자 인식을 위해 살짝 선명화
            img = img.filter(ImageFilter.SHARPEN)
            try:
                text = pytesseract.image_to_string(img, lang="eng+kor", config="--oem 3 --psm 6")
            except Exception:
                text = pytesseract.image_to_string(img, lang="eng", config="--oem 3 --psm 6")
            if text:
                ocr_text += f"\n[OCR_PAGE_{page_idx+1}]\n" + text
        doc.close()
    except Exception:
        # OCR 라이브러리 또는 Tesseract 미설치 환경에서는 기존 PDF 텍스트 추출만 사용
        return ""
    return ocr_text


def _extract_pdf_text(uploaded_file):
    data = uploaded_file.read()
    uploaded_file.seek(0)
    direct_text = _direct_extract_pdf_text(data)
    # 직접 텍스트가 부족하거나, 물성/성분 라벨이 보이지 않을 때 OCR 보조 추출 수행
    if not _pdf_text_has_useful_values(direct_text):
        ocr_text = _ocr_pdf_text(data)
        if ocr_text.strip():
            return direct_text + "\n\n[Sentinel OCR fallback text]\n" + ocr_text
    return direct_text



def _extract_pdf_tables(uploaded_file):
    data = uploaded_file.read()
    uploaded_file.seek(0)
    tables = []
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page_no, page in enumerate(pdf.pages, start=1):
                for table in page.extract_tables() or []:
                    if len(table) < 1:
                        continue
                    # 1) 일반적인 첫 행 헤더 테이블
                    if len(table) >= 2:
                        header = [str(x).strip() if x is not None else "" for x in table[0]]
                        df = pd.DataFrame(table[1:], columns=header)
                        std = _standardize_import_dataframe(df)
                        if not std.empty:
                            std["note"] = std.get("note", "").fillna("").astype(str) + f" | imported_pdf_table_page={page_no}"
                            tables.append(std)
                    # 2) 좌측 항목명 / 우측 값 형태의 key-value 테이블
                    flat_rows = []
                    for tr in table:
                        cells = ["" if c is None else str(c).strip() for c in tr]
                        if any(cells):
                            flat_rows.append(cells)
                    kv_row = {c: np.nan for c in _measured_columns()}
                    for cells in flat_rows:
                        joined = " ".join(cells)
                        for target, aliases in COLUMN_SYNONYMS.items():
                            if target not in kv_row:
                                continue
                            for alias in aliases + [target]:
                                if _norm_name(alias) and _norm_name(alias) in _norm_name(joined):
                                    # 같은 행의 마지막 숫자 또는 마지막 텍스트 셀을 값으로 사용
                                    val = np.nan
                                    nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", joined.replace(",", ""))
                                    if target.startswith("comp_") or target.startswith("actual_") or target.endswith("_mm") or target.endswith("_temp") or target.endswith("_time_min"):
                                        if nums:
                                            val = nums[-1]
                                    else:
                                        for c in reversed(cells):
                                            if c and _norm_name(c) != _norm_name(alias):
                                                val = c
                                                break
                                    if pd.notna(val):
                                        kv_row[target] = val
                                    break
                    kv_std = _standardize_import_dataframe(pd.DataFrame([kv_row]))
                    if not kv_std.empty:
                        kv_std["note"] = kv_std.get("note", "").fillna("").astype(str) + f" | imported_pdf_kv_page={page_no}"
                        tables.append(kv_std)
    except Exception:
        pass
    return tables


def _first_number_after_label(text, aliases, min_value=None, max_value=None, window=100):
    """PDF 텍스트에서 라벨 뒤쪽 가까운 숫자를 추출합니다."""
    for alias in aliases:
        pat = re.compile(re.escape(alias), flags=re.IGNORECASE)
        for m in pat.finditer(text):
            segment = text[m.end():m.end()+window].replace(",", "")
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", segment)
            for n in nums:
                try:
                    v = float(n)
                    if min_value is not None and v < min_value:
                        continue
                    if max_value is not None and v > max_value:
                        continue
                    return v
                except Exception:
                    pass
    return np.nan


def _text_row_from_pdf_text(text, file_name=""):
    """표 인식이 불완전한 PDF에서도 본문 텍스트에서 성분/기계적 물성을 보조 추출합니다."""
    row = {c: np.nan for c in _measured_columns()}
    row["note"] = f"PDF text fallback: {file_name}"
    clean = re.sub(r"[\t\r]+", " ", text or "")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in clean.split("\n") if ln.strip()]
    joined = "\n".join(lines)

    # 기본 정보
    basic_patterns = {
        "heat_no": [r"(?:Heat\s*(?:No\.?|Number)|Heat\s*No\.|Cast\s*No\.?|Lot\s*No\.?|Charge\s*No\.?|용해번호|히트번호)\s*[:：#-]?\s*([A-Za-z0-9\-_/]+)"],
        "material_grade": [r"(?:Material\s*(?:Grade|Spec(?:ification)?)?|Grade|Spec|Steel\s*Grade|재질|규격|강종)\s*[:：#-]?\s*([A-Za-z0-9\-_/ .]+)"],
        "product_name": [r"(?:Product|Item|Description|Part\s*Name|품명|제품명)\s*[:：#-]?\s*([A-Za-z0-9\-_/ .]+)"],
    }
    for key, pats in basic_patterns.items():
        for pat in pats:
            m = re.search(pat, joined, flags=re.IGNORECASE)
            if m:
                row[key] = m.group(1).strip()
                break

    # 기계적 물성: 라벨 뒤 숫자 방식
    mech_aliases = {
        "actual_ys": ["Yield Strength", "Yield", "Y.S", "YS", "Rp0.2", "Rp 0.2", "0.2% Proof", "Proof Stress", "항복강도"],
        "actual_ts": ["Tensile Strength", "Ultimate Tensile", "U.T.S", "UTS", "T.S", "TS", "Rm", "인장강도"],
        "actual_el": ["Elongation", "Elong.", "EL", "A5", "A ", "연신율", "연신"],
        "actual_ra": ["Reduction of Area", "R.A", "RA", "Z ", "단면수축률", "단면수축"],
        "actual_cvn": ["Charpy", "Impact", "KV2", "CVN", "Absorbed Energy", "흡수에너지", "충격치"],
        "actual_hb": ["Hardness", "Brinell", "HBW", "HB", "BHN", "경도", "브리넬"],
    }
    ranges = {
        "actual_ys": (100, 2000), "actual_ts": (100, 2500), "actual_el": (1, 100),
        "actual_ra": (1, 100), "actual_cvn": (1, 500), "actual_hb": (50, 700),
    }
    for key, aliases in mech_aliases.items():
        lo, hi = ranges[key]
        v = _first_number_after_label(joined, aliases, lo, hi, window=120)
        if pd.notna(v):
            row[key] = v

    # 성분: 원소 라벨 뒤 숫자 방식 + 성분 표 헤더/값 라인 방식
    for e in ELEMENT_LIST:
        # C는 텍스트 일반 문자와 혼동될 수 있으므로 단어 경계를 엄격히 사용
        m = re.search(rf"(?<![A-Za-z]){re.escape(e)}(?![A-Za-z])\s*(?:%|wt%|=|:|：)?\s*([0-9]+\.\d+|0?\.\d+|[0-9]+)", joined, flags=re.IGNORECASE)
        if m:
            val = _safe_float(m.group(1), np.nan)
            if pd.notna(val) and 0 <= val <= 10:
                row[f"comp_{e}"] = val

    # 성분 테이블: "C Si Mn P S ..." 다음 행 "0.12 0.35 ..."
    element_set = set(ELEMENT_LIST)
    for i, line in enumerate(lines):
        tokens = re.findall(r"\b[A-Z][a-z]?\b", line)
        elems = [t for t in tokens if t in element_set]
        if len(elems) >= 3:
            for j in range(i+1, min(i+4, len(lines))):
                nums = [float(x) for x in re.findall(r"(?<![A-Za-z])(?:\d+\.\d+|0?\.\d+|\d+)(?![A-Za-z])", lines[j].replace(",", ""))]
                if len(nums) >= min(3, len(elems)):
                    for e, v in zip(elems, nums):
                        if 0 <= v <= 10:
                            row[f"comp_{e}"] = v
                    break

    # 기계시험 표: 헤더 라인 다음 숫자 라인 방식
    label_map = [
        ("actual_ys", ["YS", "Yield", "Rp0.2", "Proof"]),
        ("actual_ts", ["TS", "UTS", "Tensile", "Rm"]),
        ("actual_el", ["EL", "Elong", "A5"]),
        ("actual_ra", ["RA", "Reduction", "Z"]),
        ("actual_cvn", ["CVN", "Impact", "Charpy", "KV"]),
        ("actual_hb", ["HB", "HBW", "Hardness", "Brinell", "BHN"]),
    ]
    for i, line in enumerate(lines):
        found = []
        for key, aliases in label_map:
            for a in aliases:
                pos = line.lower().find(a.lower())
                if pos >= 0:
                    found.append((pos, key))
                    break
        found = sorted(dict((k, v) for k, v in found).items()) if False else sorted(found)
        if len(found) >= 2:
            ordered_keys = [k for _, k in found]
            for j in range(i+1, min(i+5, len(lines))):
                nums = [_safe_float(x) for x in re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", lines[j].replace(",", ""))]
                nums = [x for x in nums if pd.notna(x)]
                if len(nums) >= min(2, len(ordered_keys)):
                    for key, v in zip(ordered_keys, nums):
                        lo, hi = ranges.get(key, (None, None))
                        if (lo is None or v >= lo) and (hi is None or v <= hi):
                            row[key] = v
                    break

    return _standardize_import_dataframe(pd.DataFrame([row]))


def _merge_standard_rows(primary, fallback):
    """PDF 표 추출 결과에 텍스트 fallback 결과를 병합합니다. 빈 칸은 fallback 값으로 채웁니다."""
    if primary is None or primary.empty:
        return fallback if fallback is not None else pd.DataFrame(columns=_measured_columns())
    if fallback is None or fallback.empty:
        return primary
    fb = fallback.iloc[0]
    out = primary.copy()
    for col in out.columns:
        if col in fallback.columns:
            out[col] = out[col].where(out[col].notna(), fb.get(col))
            # 빈 문자열도 fallback으로 보완
            out[col] = out[col].replace("", np.nan).where(out[col].replace("", np.nan).notna(), fb.get(col))
    return out



def _mid_temp_from_range(temp_range):
    """'895~903' 같은 온도 범위에서 평균 온도를 반환합니다."""
    try:
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(temp_range))]
        if len(nums) >= 2:
            return round((nums[0] + nums[1]) / 2.0, 1)
        if nums:
            return nums[0]
    except Exception:
        pass
    return np.nan


def _parse_dca_material_certificate(text, file_name=""):
    """대창 DCA-153-2 계열 Material Certificate 전용 파서.

    일반 PDF 표 추출기는 병합 셀 때문에 1행만 만들거나 Spec/Min. 값을 실측값으로
    오인식하는 경우가 있다. 본 파서는 다음 구조를 명시적으로 읽는다.
    - Chemical Composition: No. / Cast No.별 4개 행
    - Tensile/Impact Test: Specimen No.별 실측 YS/TS/EL/RA/CVN AVG
    - Heat Treatment: 'No. 4'와 '1,2,3'처럼 그룹으로 표시된 열처리 조건을
      각 Cast No. 행에 전개하여 4개 레코드로 만든다.
    """
    if not text or not re.search(r"MATERIAL\s+CERTIFICATE", text, re.I):
        return pd.DataFrame(columns=_measured_columns())
    if not re.search(r"Cast\s+No\.?", text, re.I) or not re.search(r"Heat\s+Treatment", text, re.I):
        return pd.DataFrame(columns=_measured_columns())

    lines = [re.sub(r"\s+", " ", ln).strip() for ln in str(text).splitlines() if ln.strip()]
    joined = "\n".join(lines)

    product_name = ""
    material_grade = ""
    cert_no = ""
    m = re.search(r"Product\s+name\s+(.+?)(?:\s+Drawing\s+No\.|$)", joined, re.I)
    if m:
        product_name = m.group(1).strip()
    m = re.search(r"Material\s+Spec\.\s+(.+?)(?:\s+ABS\s+Cert\s+No\.|$)", joined, re.I)
    if m:
        material_grade = m.group(1).strip()
    m = re.search(r"Certificate\s+No\.\s*([A-Za-z0-9\-_]+)", joined, re.I)
    if m:
        cert_no = m.group(1).strip()

    # 1) Cast No.별 화학성분
    cert_elems = ["C", "Si", "Mn", "P", "S", "Ni", "Cr", "Mo", "Cu", "V", "Al", "N", "Nb", "Ti", "Sn", "Sb", "As", "B", "SRE", "CE"]
    chem_by_no = {}
    for line in lines:
        m = re.match(r"^(\d+)\s+([A-Za-z0-9\-]+)\s+\d+\s+[\d,]+\s+Ladle\s+(.+)$", line)
        if not m:
            continue
        no = int(m.group(1))
        cast_no = m.group(2).strip()
        nums = [_safe_float(x, np.nan) for x in re.findall(r"\d+\.\d+|\d+", m.group(3))[:len(cert_elems)]]
        if len(nums) < 8:
            continue
        vals = dict(zip(cert_elems, nums))
        comp = {f"comp_{e}": np.nan for e in ELEMENT_LIST}
        # Certificate header order differs from Sentinel internal order, so assign by element symbol.
        for e in ELEMENT_LIST:
            if e in vals:
                comp[f"comp_{e}"] = vals[e]
        chem_by_no[no] = {"heat_no": cast_no, **comp, "cert_ce": vals.get("CE", np.nan), "cert_sre": vals.get("SRE", np.nan)}

    # 2) Specimen별 실측 물성. Min./Spec. 라인은 제외하고 No. E25~ 형태만 읽는다.
    mech_by_no = {}
    for line in lines:
        m = re.match(
            r"^(\d+)\s+(E\d+)\s+.*?\bRT\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+2V.*?\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)(?:\s|$)",
            line,
            flags=re.I,
        )
        if not m:
            continue
        no = int(m.group(1))
        mech_by_no[no] = {
            "section_type": m.group(2),
            "test_temp_c": -20.0 if re.search(r"-20\s*°?C|-20\s*℃|-20", line) else np.nan,
            "actual_ys": _safe_float(m.group(3), np.nan),
            "actual_ts": _safe_float(m.group(4), np.nan),
            "actual_el": _safe_float(m.group(5), np.nan),
            "actual_ra": _safe_float(m.group(6), np.nan),
            "actual_cvn": _safe_float(m.group(10), np.nan),  # 1st/2nd/3rd 뒤 AVG.
            "actual_hb": np.nan,
        }

    # 3) Heat Treatment 그룹 전개: 예) 'No. 4 1,2,3'
    ht_by_no = {}
    try:
        ht_idx = next(i for i, l in enumerate(lines) if re.fullmatch(r"Heat\s+Treatment", l, flags=re.I))
        no_line = lines[ht_idx + 1] if ht_idx + 1 < len(lines) else ""
        groups = [[int(x) for x in tok.split(",") if x.strip().isdigit()] for tok in re.findall(r"\d+(?:,\d+)*", no_line)]
        proc_alias = {
            "Preliminary": ("p0", "Normalizing", "공냉(AC)"),
            "Quenching": ("p1", "Quenching", "수냉(WQ)"),
            "Tempering": ("p2", "Tempering", "공냉(AC)"),
            "PWHT": ("p3", "PWHT", "노냉(FC)"),
        }
        for line in lines[ht_idx + 2: ht_idx + 12]:
            pm = re.match(r"^(Preliminary|Quenching|Tempering|PWHT):\s*(.*)", line, flags=re.I)
            if not pm:
                continue
            pname = pm.group(1).capitalize()
            if pname.upper() == "PWHT":
                pname = "PWHT"
            prefix, ptype, cooling = proc_alias[pname]
            vals = re.findall(r"(\d+\s*~\s*\d+)\s*˚?C\s*([0-9.]+)\s*Hr", pm.group(2), flags=re.I)
            for group_idx, nos in enumerate(groups):
                if group_idx >= len(vals):
                    continue
                temp_range, hr = vals[group_idx]
                temp = _mid_temp_from_range(temp_range)
                time_min = round(_safe_float(hr, 0.0) * 60.0, 1)
                for no in nos:
                    ht_by_no.setdefault(no, {})[f"{prefix}_type"] = ptype
                    ht_by_no.setdefault(no, {})[f"{prefix}_temp"] = temp
                    ht_by_no.setdefault(no, {})[f"{prefix}_time_min"] = time_min
                    ht_by_no.setdefault(no, {})[f"{prefix}_cooling"] = cooling
                    ht_by_no.setdefault(no, {})[f"{prefix}_note"] = f"{temp_range}C x {hr}Hr"
    except Exception:
        ht_by_no = {}

    nos = sorted(set(chem_by_no) | set(mech_by_no) | set(ht_by_no))
    if len(nos) < 2:
        return pd.DataFrame(columns=_measured_columns())

    rows = []
    for no in nos:
        row = {c: np.nan for c in _measured_columns()}
        row["material_grade"] = material_grade or np.nan
        row["product_name"] = product_name or np.nan
        if no in chem_by_no:
            row.update({k: v for k, v in chem_by_no[no].items() if k in row})
        if no in mech_by_no:
            row.update({k: v for k, v in mech_by_no[no].items() if k in row})
        if no in ht_by_no:
            row.update({k: v for k, v in ht_by_no[no].items() if k in row})
        ht_note = "; ".join([v for k, v in ht_by_no.get(no, {}).items() if k.endswith("_note")])
        row["note"] = f"DCA material certificate parser | source={file_name} | cert_no={cert_no} | no={no}"
        if ht_note:
            row["note"] += f" | HT={ht_note}"
        rows.append(row)

    return pd.DataFrame(rows)[_measured_columns()]

def parse_pdf_certificate(uploaded_file):
    """PDF MTR/시험성적서에서 전용 양식 파서 + 표 + 본문 텍스트를 같이 사용해 추출합니다."""
    text = _extract_pdf_text(uploaded_file)

    # DAECHANG DCA-153-2 Material Certificate처럼 Cast No./기계시험/열처리가
    # 서로 다른 표 블록에 있는 양식은 전용 파서를 먼저 사용한다.
    dca_df = _parse_dca_material_certificate(text, uploaded_file.name) if text.strip() else pd.DataFrame(columns=_measured_columns())
    if dca_df is not None and not dca_df.empty:
        return dca_df

    text_df = _text_row_from_pdf_text(text, uploaded_file.name) if text.strip() else pd.DataFrame(columns=_measured_columns())
    table_frames = _extract_pdf_tables(uploaded_file)
    if table_frames:
        table_df = pd.concat(table_frames, ignore_index=True)
        merged = _merge_standard_rows(table_df, text_df)
    else:
        merged = text_df
    # 중복/완전 공백 제거
    if merged is None or merged.empty:
        return pd.DataFrame(columns=_measured_columns())
    useful_cols = ["heat_no"] + [f"comp_{e}" for e in ["C", "Si", "Mn", "Ni", "Cr", "Mo"]] + [f"actual_{k}" for k in PROP_KEYS]
    mask = pd.Series(False, index=merged.index)
    for c in useful_cols:
        if c in merged.columns:
            mask = mask | merged[c].notna()
    return merged[mask].copy()

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
        force_manual_thickness = bool(default_meta.get("force_manual_thickness", False))
        if force_manual_thickness:
            thickness_value = default_meta.get("thickness_mm", 150)
            coupon_thick_value = default_meta.get("coupon_thickness_mm", 50)
            thickness_note = f" | thickness_manual_override: product={thickness_value}mm, coupon={coupon_thick_value}mm"
        else:
            thickness_value = _safe_float(r.get("thickness_mm"), default_meta.get("thickness_mm", 150))
            coupon_thick_value = _safe_float(r.get("coupon_thickness_mm"), default_meta.get("coupon_thickness_mm", 50))
            thickness_note = ""

        rows.append(build_measured_record(
            heat_no=str(r.get("heat_no") if pd.notna(r.get("heat_no")) else ""),
            material_grade=str(r.get("material_grade") if pd.notna(r.get("material_grade")) else default_meta.get("material_grade", "Imported")),
            product_name=str(r.get("product_name") if pd.notna(r.get("product_name")) else default_meta.get("product_name", "Imported Casting")),
            section_type=str(r.get("section_type") if pd.notna(r.get("section_type")) else default_meta.get("section_type", "Coupon")),
            comp=comp, p0=p0, p1=p1, p2=p2, p3=p3,
            thickness=thickness_value,
            coupon_thick=coupon_thick_value,
            test_temp=_safe_float(r.get("test_temp_c"), default_meta.get("test_temp_c", -46)),
            actuals=actuals,
            note=(str(r.get("note") if pd.notna(r.get("note")) else "자동 업로드 반영") + thickness_note)
        ))
    return pd.DataFrame(rows)[_measured_columns()] if rows else pd.DataFrame(columns=_measured_columns())



# [PAGE CONFIG]
st.set_page_config(page_title="Sentinel-Alpha v6.6.4", layout="wide")

# [CSS CUSTOM STYLE]
st.markdown("""
    <style>
    .stMetric { background-color: #1e293b; padding: 15px; border-radius: 10px; border: 1px solid #334155; color: white; }
    .stMetric label { color: #94a3b8 !important; font-weight: bold; }
    .stMetric [data-testid="stMetricValue"] { color: #ffffff !important; font-weight: 800; }
    .main-title { color: #1e3a8a; font-size: 32px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">🛡️ Sentinel-Alpha v6.6.4: 전문가용 전공정 시뮬레이터</p>', unsafe_allow_html=True)

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
    st.caption("MTR, 기계시험 성적서, Heat 성분표를 Excel 또는 PDF로 업로드하면 Heat No., 성분, 열처리, 실측 물성을 자동 추출합니다. 이미지/스캔 PDF는 OCR로 보조 인식합니다. 본품 두께와 Coupon 두께는 파일에서 읽지 않고 아래 수동 입력값을 강제 적용합니다.")

    st.info("📌 업로드 파일의 두께 표기는 양식별 의미가 다를 수 있으므로, 보정 DB에는 아래에 입력한 본품 두께와 Coupon 두께가 우선 적용됩니다.")
    th_col1, th_col2, th_col3 = st.columns(3)
    upload_product_thickness = th_col1.number_input("업로드 데이터 본품 두께(mm)", 10, 2500, input_thickness, key="upload_product_thickness")
    upload_coupon_thickness = th_col2.number_input("업로드 데이터 Coupon 두께(mm)", 10, 2500, input_coupon_thick, key="upload_coupon_thickness")
    upload_force_thickness = th_col3.checkbox("파일 내 두께값 무시하고 위 두께 적용", value=True, key="upload_force_thickness")

    up_col1, up_col2 = st.columns([2, 1])
    uploaded_file = up_col1.file_uploader("실측 성적서 업로드", type=["xlsx", "xls", "csv", "pdf"], help="권장: Excel은 첫 행에 C, Si, Mn, YS, TS, EL, RA, CVN, HB 등 컬럼명을 넣으면 가장 정확합니다.")
    with up_col2:
        st.write("자동 인식 가능 항목")
        st.caption("Heat No. / 재질 / C~Zr 20원소 / 열처리 조건 / YS·TS·EL·RA·CVN·HB")
        st.caption("두께: 위 수동 입력값 적용")

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
                    "thickness_mm": upload_product_thickness, "coupon_thickness_mm": upload_coupon_thickness, "force_manual_thickness": upload_force_thickness, "test_temp_c": actual_test_temp,
                    "p0_type": a_p0_type, "p0_temp": a_p0_temp, "p0_time_min": a_p0_time, "p0_cooling": a_p0_cool,
                    "p1_type": a_p1_type, "p1_temp": a_p1_temp, "p1_time_min": a_p1_time, "p1_cooling": a_p1_cool,
                    "p2_type": a_p2_type, "p2_temp": a_p2_temp, "p2_time_min": a_p2_time, "p2_cooling": a_p2_cool,
                    "p3_type": a_p3_type, "p3_temp": a_p3_temp, "p3_time_min": a_p3_time, "p3_cooling": a_p3_cool,
                }
                if upload_force_thickness:
                    parsed_df["thickness_mm"] = upload_product_thickness
                    parsed_df["coupon_thickness_mm"] = upload_coupon_thickness
                completed_df = _complete_import_rows(parsed_df, default_meta=default_meta)
                st.success(f"자동 추출 완료: 후보 {len(parsed_df)}행 / 보정 DB 반영 가능 {len(completed_df)}행")
                if upload_force_thickness:
                    st.caption(f"두께 적용 방식: 파일 내 두께값 무시 → 본품 {upload_product_thickness} mm / Coupon {upload_coupon_thickness} mm 적용")
                st.write("#### 추출 미리보기")
                preview_cols = ["heat_no", "material_grade", "product_name", "thickness_mm", "comp_C", "comp_Si", "comp_Mn", "actual_ys", "actual_ts", "actual_el", "actual_ra", "actual_cvn", "actual_hb", "note"]
                st.dataframe(completed_df[[c for c in preview_cols if c in completed_df.columns]], use_container_width=True, hide_index=True)

                if st.button("✅ 미리보기 데이터 누적 DB 반영", use_container_width=True):
                    if completed_df.empty:
                        st.error("보정 DB에 반영 가능한 실측 물성값이 없습니다. PDF/Excel에서 YS, TS, EL, RA, CVN, HB 중 최소 1개 이상이 추출되어야 합니다.")
                    else:
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
    st.write("- 업로드 자동 반영 시 본품 두께와 Coupon 두께는 파일 추출값이 아니라 사용자가 입력한 값으로 강제 적용할 수 있습니다.")
    st.write("- PDF 자동 추출은 성적서 양식과 이미지 품질에 따라 인식률 차이가 있으므로, OCR 결과 포함 미리보기 값을 반드시 확인한 뒤 DB에 반영하는 구조로 설계했습니다.")
    st.warning("주의: 데이터가 적을 때는 보정 신뢰도가 낮습니다. 최소 3건 이상부터 보정이 적용되며, 동일 재질·동일 열처리·유사 두께 데이터가 많을수록 정확도가 높아집니다.")
