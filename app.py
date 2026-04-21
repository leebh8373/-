import streamlit as st
import pandas as pd
import calculations as calc

st.set_page_config(page_title="Sentinel-Alpha Ultimate Master v4.0", layout="wide")
st.title("🛡️ Sentinel-Alpha: 전공정 물성 예측 및 역설계 통합 시스템")

t_sim, t_inv = st.tabs(["📊 물성 예측 시뮬레이션", "🔄 정밀 역설계 엔진"])

with t_sim:
    st.header("1️⃣ 20종 화학 성분 정밀 입력")
    comp = {}
    row_cols = [st.columns(5) for _ in range(4)]
    elements = ['C', 'Si', 'Mn', 'P', 'S', 'Cr', 'Mo', 'Ni', 'Cu', 'V', 'Nb', 'Ti', 'Al', 'B', 'N', 'As', 'Sn', 'Sb', 'Pb', 'Zr']
    for i, el in enumerate(elements):
        comp[el] = row_cols[i//5][i%5].number_input(f"{el} (%)", 0.0, 30.0, 0.20 if el=='C' else 0.0, format="%.4f")

    st.divider()
    st.header("2️⃣ 1~3차 공정 변수 (가열 온도 및 냉각 방식 전수 포함)")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("1차 메인 열처리")
        p1_temp = st.number_input("가열 온도 (℃)", 800, 1250, 930, key="p1_t")
        p1_time = st.number_input("유지 시간 (min)", 10, 10000, 360, key="p1_m")
        p1_cool = st.selectbox("냉각 방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)", "노냉(FC)"], key="p1_c")
    with c2:
        st.subheader("2차 후속 공정")
        p2_type = st.selectbox("2차 종류", ["None", "Tempering", "S/R", "PWHT"], key="p2_tp")
        p2_temp = st.number_input("2차 온도 (℃)", 0, 950, 610, key="p2_t")
        p2_time = st.number_input("2차 시간 (min)", 0, 10000, 240, key="p2_m")
        p2_cool = st.selectbox("2차 냉각 방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)", "노냉(FC)"], key="p2_c")
    with c3:
        st.subheader("3차 추가 공정")
        p3_type = st.selectbox("3차 종류", ["None", "S/R", "PWHT"], key="p3_tp")
        p3_temp = st.number_input("3차 온도 (℃)", 0, 950, 620, key="p3_t")
        p3_time = st.number_input("3차 시간 (min)", 0, 10000, 300, key="p3_m")
        p3_cool = st.selectbox("3차 냉각 방식", ["수냉(WQ)", "공냉(AC)", "노냉(FC)"], key="p3_c")

    st.divider()
    thick = st.number_input("주물 최대 단면 두께 (mm)", 10, 2000, 150)
    test_t = st.selectbox("충격 시험 온도 (℃)", [20, 0, -20, -46, -60, -110])

    if st.button("🚀 시뮬레이션 가동", use_container_width=True):
        ts_1 = calc.calculate_1st_stage_physics("Carbon", comp, {'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool}, thick)
        res = calc.get_final_expert_simulation("Carbon", ts_1, 
                                               {'type':p2_type, 'temp':p2_temp, 'time':p2_time, 'cooling':p2_cool},
                                               {'type':p3_type, 'temp':p3_temp, 'time':p3_time, 'cooling':p3_cool},
                                               test_t, comp)
        
        st.success("### [최종 기계적 물성 리포트]")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("강도 (YS / TS)", f"{res['ys']} / {res['ts']} MPa")
        r2.metric("연성 (EL / RA)", f"{res['el']} / {res['ra']} %")
        r3.metric("경도 (HB)", f"{res['hb']}")
        r4.metric("인성 (CVN)", f"{res['cvn']} J")
        st.info(f"**금속 조직:** {res['org']} / **격자 구조:** {res['lat']}")

with t_inv:
    st.header("🔄 목표 물성 기반 정밀 역설계 엔진")
    ic1, ic2, ic3 = st.columns(3)
    t_ys = ic1.number_input("목표 YS (MPa)", 300, 1200, 485)
    t_ts = ic1.number_input("목표 TS (MPa)", 400, 1500, 620)
    t_el = ic2.number_input("목표 EL (%)", 10, 45, 22)
    t_ra = ic2.number_input("목표 RA (%)", 20, 85, 45)
    t_hb = ic3.number_input("목표 HB", 100, 550, 195)
    t_cvn = ic3.number_input("목표 CVN (J)", 20, 300, 60)

    if st.button("🔍 최적 성분 및 전공정 조건 역설계", use_container_width=True):
        inv_res = calc.run_expert_inverse_engine({'ys':t_ys, 'ts':t_ts, 'el':t_el, 'ra':t_ra, 
                                                 'hb':t_hb, 'cvn':t_cvn, 'test_temp':test_t, 'thick':thick})
        st.success("### [역설계 추천 리포트]")
        st.write("#### 1. 추천 화학 성분 설계 (20종 가이드)")
        st.table(pd.DataFrame([inv_res['alloy']]))
        st.write("#### 2. 추천 전공정 열처리 시나리오 (냉각 방식 포함)")
        st.json(inv_res['p1']); st.json(inv_res['p2']); st.json(inv_res['p3'])