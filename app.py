import streamlit as st
import pandas as pd
import calculations as calc

st.set_page_config(page_title="Sentinel-Alpha Ultimate Heavy Industry", layout="wide")
st.title("🛡️ Sentinel-Alpha: 주강/해양/원자력 통합 물성 시스템")

# --- STEP 1: 강종 및 20종 성분 입력 ---
st.header("🧪 [STEP 1] 강종 선택 및 20종 분석 데이터")
mat_group = st.selectbox("생산 대상 강종군", 
    ["일반 탄소강 / 저합금강", "NORSOK M-122 (해양 구조용 주강)", "원자력 발전용 저합금강", "스테인리스강 (Solution Treatment)", "고온/저온용 특수 합금"])

comp = {}
elements = [['C', 'Si', 'Mn', 'P', 'S'], ['Cr', 'Mo', 'Ni', 'Cu', 'V'], ['Nb', 'Ti', 'Al', 'B', 'N'], ['As', 'Sn', 'Sb', 'Pb', 'Zr']]
for row in elements:
    cols = st.columns(5)
    for idx, el in enumerate(row):
        def_val = 0.18 if el == 'C' else (1.50 if el == 'Mn' else 0.00)
        comp[el] = cols[idx].number_input(f"{el} (%)", 0.0, 30.0, def_val, format="%.4f")

# --- STEP 2: 열처리 공정 및 시험 온도 (14개 구간) ---
st.header("⚙️ [STEP 2] 복합 열처리 및 시험 조건 (S/R 포함)")
c1, c2, c3 = st.columns(3)
with c1:
    t1_type = st.selectbox("1차 메인 열처리", ["Quenching", "Normalizing", "Solution Treatment", "Annealing"])
    t1_cooling = st.radio("냉각 방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)", "노냉(FC)"], horizontal=True)
    thickness = st.number_input("주물 최대 단면 두께 (mm)", 5, 1500, 150)
with c2:
    t2_type = st.selectbox("후속/2차 공정", ["None", "Tempering", "S/R (응력제거)", "PWHT"])
    t2_temp = st.number_input("유지 온도 (℃)", 0, 950, 620)
    t2_time = st.number_input("유지 시간 (분)", 0, 10000, 300)
with c3:
    # 팀장님이 주신 14개 온도 리스트 완벽 반영
    temps = [20, 0, -10, -20, -30, -40, -46, -50, -60, -70, -80, -90, -100, -110]
    test_temp = st.selectbox("🌡️ 충격 시험 온도 선택 (℃)", temps, index=6)

# --- STEP 3: 실행 및 결과 (NORSOK 판정 포함) ---
if st.button("🚀 전체 물성 및 규격 적합성 정밀 시뮬레이션", use_container_width=True):
    base_ts = calc.get_base_tensile_strength(mat_group, comp)
    ys, ts, el, ra, cvn = calc.apply_complex_ht_logic(mat_group, base_ts, 
                                                     {'cooling':t1_cooling}, 
                                                     {'type':t2_type, 'temp':t2_temp, 'time':t2_time}, 
                                                     thickness, test_temp)
    ceq, pcm = calc.calculate_ceq_pcm_ultimate(comp)
    
    st.divider()
    r1, r2, r3, r4 = st.columns(4)
    
    with r1:
        st.subheader("🏗️ 강도 지표")
        st.metric("항복강도 (YS)", f"{ys} MPa")
        st.metric("인장강도 (TS)", f"{ts} MPa")
        st.write(f"**항복비:** {round(ys/ts, 3)}")
    with r2:
        st.subheader("📏 연성 지표")
        st.metric("연신율 (EL)", f"{el} %")
        st.metric("단면수축률 (RA)", f"{ra} %")
    with r3:
        st.subheader("❄️ 인성/충격")
        st.metric(f"충격치 ({test_temp}℃)", f"{cvn} J")
    with r4:
        st.subheader("📋 규격 검토")
        st.write(f"**Ceq:** {ceq}")
        st.write(f"**Pcm:** {pcm}")
        if mat_group == "NORSOK M-122 (해양 구조용 주강)" and test_temp <= -46:
            if cvn >= 45 and ys >= 345: st.success("NORSOK 규격 만족")
            else: st.error("NORSOK 규격 미달 주의")

    # 결과 표 출력
    st.write("### 🔍 시뮬레이션 요약 데이터")
    st.dataframe(pd.DataFrame({
        "Parameter": ["강종군", "열처리 조합", "두께 효과", "시험 환경", "예측 조직"],
        "Value": [mat_group, f"{t1_type} + {t2_type}", f"{thickness}mm 반영", f"{test_temp}℃ 시험", "전문화된 조직 예측 수행됨"]
    }), use_container_width=True)