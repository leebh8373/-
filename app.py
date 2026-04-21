import streamlit as st
from calculations import calculate_alloy_factors, calculate_hjp, calculate_combined_hjp
from predictor import predict_properties, suggest_heat_treatment

st.set_page_config(page_title="Sentinel-Alpha 품질 시스템", layout="wide")
st.title("🛡️ 주강품 정밀 분석 및 열처리 설계 시스템")

# --- 🧪 1. 화학 성분 입력 ---
st.subheader("🧪 1. 화학 성분 및 규격 설정")
c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
with c1: c = st.number_input("C (wt%)", 0.0, 1.0, 0.210, format="%.3f")
with c2: mn = st.number_input("Mn (wt%)", 0.0, 2.5, 1.200, format="%.3f")
with c3: si = st.number_input("Si (wt%)", 0.0, 1.0, 0.400, format="%.3f")
with c4: cr = st.number_input("Cr (wt%)", 0.0, 3.0, 0.500, format="%.3f")
with c5: mo = st.number_input("Mo (wt%)", 0.0, 1.5, 0.200, format="%.3f")
with c6: ni = st.number_input("Ni (wt%)", 0.0, 5.0, 0.300, format="%.3f")
with c7: v = st.number_input("V (wt%)", 0.0, 0.5, 0.020, format="%.3f")
with c8: b = st.number_input("B (wt%)", 0.0, 0.01, 0.000, format="%.4f")

# --- [추가/복구] Ceq 계산 규격 선택란 ---
st.markdown("##### 📏 Ceq 계산 규격 선택")
comp = {'C':c, 'Mn':mn, 'Si':si, 'Cr':cr, 'Mo':mo, 'Ni':ni, 'V':v, 'B':b}
ceq_all, pcm_val = calculate_alloy_factors(comp)

# 규격 선택 라디오 버튼 (가로 배치)
ceq_standard = st.radio(
    "적용할 Ceq 규격을 선택하십시오", 
    options=list(ceq_all.keys()), 
    horizontal=True,
    help="선택한 규격에 따라 물성 예측 가중치가 달라집니다."
)
selected_ceq = ceq_all[ceq_standard]

st.markdown("---")

# --- ⚙️ 모드 선택 및 공정 입력 ---
mode = st.radio("⚙️ 분석 모드 선택", ["물성 예측 (Forward)", "열처리 역설계 (Reverse)"], horizontal=True)

if mode == "물성 예측 (Forward)":
    st.subheader("🔥 2. 프로세스 처리 (처리 내역)")
    p1, p2, p3, p4 = st.columns([1.5, 1, 1, 2])
    with p1: p_type = st.selectbox("1차 공정", ["Annealing", "Normalizing", "Solution Annealing", "Quenching (Oil)", "Quenching (Water)"])
    with p2: thickness = st.number_input("유효 두께 (mm)", 10, 500, 100)
    with p3: t_cool_sel = st.selectbox("템퍼링 냉각", ["공냉 (Air)", "노냉 (Furnace)"])
    
    is_quenching = "Quenching" in p_type
    extra_options = ["S/R", "PWHT"]
    if not is_quenching:
        extra_options = ["Tempering"] + extra_options
    with p4: extra_list = st.multiselect("추가 선택 옵션", extra_options)

    st.markdown("##### 🌡️ 세부 열처리 조건")
    cond1, cond2, cond3, cond4, cond5, cond6 = st.columns(6)
    hjp_list = []

    if is_quenching or "Tempering" in extra_list:
        with cond1: t_temp = st.number_input("Tempering T(°C)", 400, 750, 620)
        with cond2: t_time = st.number_input("Tempering t(hr)", 0.5, 24.0, 4.0)
        hjp_list.append(calculate_hjp(t_temp, t_time))

    if "S/R" in extra_list:
        with cond3: sr_temp = st.number_input("S/R T(°C)", 400, 750, 580)
        with cond4: sr_time = st.number_input("S/R t(hr)", 1.0, 24.0, 2.0)
        hjp_list.append(calculate_hjp(sr_temp, sr_time))
    
    if "PWHT" in extra_list:
        with cond5: pw_temp = st.number_input("PWHT T(°C)", 400, 750, 605)
        with cond6: pw_time = st.number_input("PWHT t(hr)", 1.0, 100.0, 6.0)
        hjp_list.append(calculate_hjp(pw_temp, pw_time))

    # 연산
    c_hjp = calculate_combined_hjp(hjp_list)
    res = predict_properties(selected_ceq, pcm_val, c_hjp, thickness, p_type, t_cool_sel, extra_list)

    # --- 결과 출력 ---
    st.markdown("---")
    st.subheader("📊 예측 결과 요약")
    sum1, sum2, sum3, sum4 = st.columns(4)
    sum1.metric("PCM (용접성)", f"{pcm_val:.3f}")
    sum2.metric(f"적용 Ceq ({ceq_standard})", f"{selected_ceq:.3f}")
    sum3.metric("누적 HJP", f"{c_hjp:.2f}")
    sum4.metric("잔류 응력 (RS)", f"{res['RS']} MPa")

    st.markdown("##### 🚀 최종 기계적 물성")
    res_cols = st.columns(6)
    metrics = [("인장강도(TS)", "TS", "MPa"), ("항복강도(YS)", "YS", "MPa"), ("연신율(EL)", "EL", "%"), 
               ("단면수축(RA)", "RA", "%"), ("충격치(CVN)", "CVN", "J"), ("경도(HB)", "HB", "HB")]
    for i, (label, key, unit) in enumerate(metrics):
        res_cols[i].metric(label, f"{res[key]} {unit}")

else:
    st.subheader("🎯 2. 목표 물성 입력 (Reverse Design)")
    t1, t2, t3 = st.columns(3)
    with t1: target_ts = st.number_input("목표 인장강도 (TS, MPa)", 300, 1000, 500)
    with t2: target_cvn = st.number_input("목표 충격치 (CVN, J)", 10, 300, 50)
    with t3: thickness_req = st.number_input("설계 두께 (mm)", 10, 500, 100)

    if st.button("🚀 최적 열처리 조건 도출"):
        suggestion = suggest_heat_treatment(selected_ceq, target_ts, target_cvn, thickness_req)
        st.success("✅ 최적화된 열처리 제안")
        s1, s2, s3, s4 = st.columns(4)
        s1.info(f"**권장 공정**\n\n{suggestion['primary']}")
        s2.info(f"**템퍼링 온도**\n\n{suggestion['temp']} °C")
        s3.info(f"**유지 시간**\n\n{suggestion['time']} hr")
        s4.info(f"**냉각 방식**\n\n{suggestion['cooling']}")