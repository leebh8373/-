import streamlit as st
import pandas as pd
import calculations as calc

st.set_page_config(page_title="Sentinel-Alpha Pro", layout="wide")
st.title("🛡️ Sentinel-Alpha: 고도화된 물성 예측 및 역설계 시스템")

tab1, tab2 = st.tabs(["📊 물성 예측 모드", "🔄 역설계 엔진 모드"])

with tab1:
    st.header("성분 및 공정 변수 입력")
    c1, c2, c3 = st.columns(3)
    with c1:
        c = st.number_input("C (%)", 0.0, 1.0, 0.22)
        mn = st.number_input("Mn (%)", 0.0, 2.0, 1.45)
    with c2:
        cr = st.number_input("Cr (%)", 0.0, 2.0, 0.45)
        mo = st.number_input("Mo (%)", 0.0, 1.0, 0.15)
    with c3:
        thickness = st.number_input("두께 (mm)", 5, 500, 40)
        test_temp = st.selectbox("충격시험 온도 (℃)", [20, 0, -10, -20, -30, -40, -46, -60, -100])

    p1, p2 = st.columns(2)
    treatment = p1.selectbox("열처리", ["Annealing", "Normalizing", "Q&T"])
    cooling = p2.selectbox("냉각 방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)", "노냉(FC)"])

    if st.button("예측 실행"):
        comp = {'C':c, 'Mn':mn, 'Cr':cr, 'Mo':mo}
        ys, ts, el, ra = calc.calculate_properties(comp, treatment, thickness, cooling)
        cvn = calc.predict_cvn(60, test_temp)
        org, lattice = calc.predict_structure_and_lattice(treatment, cooling)
        h_time = calc.calculate_holding_time(thickness)

        st.divider()
        res1, res2, res3 = st.columns(3)
        res1.metric("항복강도 (YS)", f"{ys} MPa")
        res1.metric("인장강도 (TS)", f"{ts} MPa")
        res2.metric("연신율 (El)", f"{el} %")
        res2.metric("단면수축률 (RA)", f"{ra} %")
        res3.metric(f"충격치 ({test_temp}℃)", f"{cvn} J")
        
        st.info(f"🔬 **최종 조직:** {org}  |  💎 **격자 구조:** {lattice}  |  ⏱️ **유지 시간:** {h_time}분")

with tab2:
    st.header("목표 물성 기반 역설계")
    r1, r2 = st.columns(2)
    with r1:
        target_ts = st.number_input("목표 인장강도(TS)", 400, 1200, 600, key="r_ts")
        target_thick = st.number_input("설계 두께(mm)", 5, 500, 50, key="r_thick")
    with r2:
        target_treat = st.selectbox("희망 열처리", ["Annealing", "Normalizing", "Q&T"], key="r_treat")
        target_temp = st.selectbox("충격시험 온도", [20, 0, -10, -20, -40, -46, -100], key="r_temp")

    if st.button("역설계 실행"):
        res = calc.reverse_design_logic(target_ts, target_thick, target_treat)
        st.success("🎯 최적 설계 제안")
        
        d1, d2 = st.columns(2)
        with d1:
            st.table(pd.DataFrame({
                "항목": ["권장 C", "권장 Mn", "권장 Cr", "목표 Ceq"],
                "값": [res['C'], res['Mn'], res['Cr'], res['Ceq']]
            }))
        with d2:
            st.info(f"✅ **필수 유지시간:** {res['Time']} 분")
            st.info(f"✅ **예측 조직:** {res['Org']}")
            st.info(f"✅ **격자 구조:** {res['Lattice']}")