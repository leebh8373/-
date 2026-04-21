import streamlit as st
import pandas as pd
import calculations as calc

st.set_page_config(page_title="Sentinel-Alpha Ultimate Master", layout="wide")
st.title("🛡️ Sentinel-Alpha: 고도화된 물성 예측 및 전공정 역설계 시스템")

t1, t2 = st.tabs(["📊 물성 예측 모드", "🔄 정밀 역설계 엔진"])

with t1:
    st.header("1️⃣ 20종 화학 성분 및 공정 변수 입력")
    # 20종 원소를 그리드로 전체 배치
    comp = {}
    rows = [st.columns(5) for _ in range(4)]
    elements = ['C', 'Si', 'Mn', 'P', 'S', 'Cr', 'Mo', 'Ni', 'Cu', 'V', 'Nb', 'Ti', 'Al', 'B', 'N', 'As', 'Sn', 'Sb', 'Pb', 'Zr']
    for i, el in enumerate(elements):
        comp[el] = rows[i//5][i%5].number_input(f"{el} (%)", 0.0, 30.0, 0.20 if el=='C' else 0.0, format="%.4f")

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("1차 메인 열처리")
        p1_t = st.selectbox("공정", ["Quenching", "Normalizing", "Solution"])
        p1_time = st.number_input("유지시간 (min)", 10, 10000, 300)
        p1_cool = st.selectbox("냉각방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)", "노냉(FC)"])
    with c2:
        st.subheader("2차 후속 공정")
        p2_t = st.selectbox("2차 종류", ["None", "Tempering", "S/R", "PWHT"])
        p2_temp = st.number_input("2차 온도 (℃)", 0, 900, 600)
        p2_time = st.number_input("2차 시간 (min)", 0, 10000, 240)
    with c3:
        st.subheader("3차 추가 공정")
        p3_t = st.selectbox("3차 종류", ["None", "S/R", "PWHT"])
        p3_temp = st.number_input("3차 온도 (℃)", 0, 900, 620)
        p3_time = st.number_input("3차 시간 (min)", 0, 10000, 300)

    thick = st.number_input("주물 최대 두께 (mm)", 10, 1500, 150)
    test_temp = st.selectbox("충격 온도 (℃)", [20, 0, -20, -46, -60, -110])

    if st.button("🚀 시뮬레이션 가동", use_container_width=True):
        ts_1 = calc.get_detailed_base_strength("Carbon", comp, {'time':p1_time, 'cooling':p1_cool}, thick)
        res = calc.get_final_simulation("Carbon", ts_1, {'type':p2_t, 'temp':p2_temp, 'time':p2_time}, 
                                        {'type':p3_t, 'temp':p3_temp, 'time':p3_time}, test_temp, comp)
        
        st.success("### [최종 물성 리포트]")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("YS / TS", f"{res['ys']} / {res['ts']} MPa")
        r2.metric("EL / RA", f"{res['el']} / {res['ra']} %")
        r3.metric("Hardness", f"{res['hb']} HB")
        r4.metric("CVN", f"{res['cvn']} J")
        st.info(f"**조직:** {res['org']} / **격자:** {res['lat']}")

with t2:
    st.header("🔄 목표 물성 → 최적 성분/공정 역설계")
    ic1, ic2, ic3 = st.columns(3)
    target_ys = ic1.number_input("목표 YS (MPa)", 300, 1200, 450)
    target_ts = ic1.number_input("목표 TS (MPa)", 400, 1500, 600)
    target_el = ic2.number_input("목표 연신율 (%)", 10, 45, 22)
    target_ra = ic2.number_input("목표 RA (%)", 20, 80, 45)
    target_hb = ic3.number_input("목표 HB 경도", 100, 500, 180)
    target_cvn = ic3.number_input("목표 충격치 (J)", 20, 250, 50)
    
    if st.button("🔍 최적 조건 도출 실행", use_container_width=True):
        inv_res = calc.run_expert_inverse_engine({'ys':target_ys, 'ts':target_ts, 'el':target_el, 
                                                 'ra':target_ra, 'hb':target_hb, 'cvn':target_cvn, 
                                                 'test_temp':test_temp, 'thick':thick})
        st.success("### [역설계 추천 설계안]")
        st.write("#### 1. 추천 화학 성분 범위")
        st.table(pd.DataFrame([inv_res['comp']]))
        st.write("#### 2. 추천 열처리 시나리오")
        st.json(inv_res['p1']); st.json(inv_res['p2']); st.json(inv_res['p3'])