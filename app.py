import streamlit as st
import pandas as pd
import calculations as calc

st.set_page_config(page_title="Sentinel-Alpha v6.0 Reliability Mode", layout="wide")
st.title("🛡️ Sentinel-Alpha v6.0: 전문가용 전공정 물성 시뮬레이터")
st.info("※ 본 시스템은 27년 경력의 품질 관리 노하우를 기반으로 20종 원소와 1~3차 전공정 변수를 개별 연산합니다.")

t1, t2 = st.tabs(["🚀 정밀 물성 예측", "🔄 전공정 역설계 ENGINE"])

with t1:
    st.header("1️⃣ STEP 1: 화학 성분 설계 (20 Elements)")
    comp = {}
    row_1 = st.columns(5); row_2 = st.columns(5); row_3 = st.columns(5); row_4 = st.columns(5)
    all_elements = ['C', 'Si', 'Mn', 'P', 'S', 'Cr', 'Mo', 'Ni', 'Cu', 'V', 'Nb', 'Ti', 'Al', 'B', 'N', 'As', 'Sn', 'Sb', 'Pb', 'Zr']
    for i, el in enumerate(all_elements):
        target_col = [row_1, row_2, row_3, row_4][i//5][i%5]
        comp[el] = target_col.number_input(f"{el} (%)", 0.0, 30.0, 0.20 if el=='C' else 0.0, format="%.4f")

    st.divider()
    st.header("2️⃣ STEP 2: 1~3차 복합 열처리 및 냉각 조건")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("1차 메인 열처리 (Main HT)")
        p1_type = st.selectbox("열처리 종류", ["Quenching", "Normalizing", "Annealing", "Solution Treatment"])
        p1_temp = st.number_input("가열 온도 (℃)", 800, 1300, 930)
        p1_time = st.number_input("유지 시간 (min)", 10, 10000, 360)
        p1_cool = st.selectbox("1차 냉각 방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)", "노냉(FC)"])
        
    with c2:
        st.subheader("2차 후속 공정 (2nd Process)")
        p2_type = st.selectbox("2차 종류", ["None", "Tempering", "S/R", "PWHT"])
        p2_temp = st.number_input("2차 유지온도 (℃)", 0, 1000, 610)
        p2_time = st.number_input("2차 유지시간 (min)", 0, 10000, 240)
        p2_cool = st.selectbox("2차 냉각 방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)", "노냉(FC)"])
        
    with c3:
        st.subheader("3차 추가 공정 (3rd Process)")
        p3_type = st.selectbox("3차 종류", ["None", "S/R", "PWHT"])
        p3_temp = st.number_input("3차 유지온도 (℃)", 0, 1000, 620)
        p3_time = st.number_input("3차 유지시간 (min)", 0, 10000, 300)
        p3_cool = st.selectbox("3차 냉각 방식", ["수냉(WQ)", "공냉(AC)", "노냉(FC)"])

    st.divider()
    m1, m2 = st.columns(2)
    thick = m1.number_input("주물 최대 단면 두께 (mm)", 10, 2500, 150)
    test_t = m2.selectbox("충격 시험 온도 (℃)", [20, 10, 0, -10, -20, -30, -46, -60, -110])

    if st.button("📊 시뮬레이션 가동 및 신뢰성 검증", use_container_width=True):
        # 1단계 계산
        ts_1 = calc.calculate_1st_stage_physics("Carbon", comp, 
                                                {'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool}, thick)
        # 최종 단계 계산
        res = calc.get_final_expert_simulation("Carbon", ts_1, 
                                               {'type':p2_type, 'temp':p2_temp, 'time':p2_time, 'cooling':p2_cool},
                                               {'type':p3_type, 'temp':p3_temp, 'time':p3_time, 'cooling':p3_cool},
                                               test_t, comp)
        
        st.success("### [최종 기계적 물성 예측 리포트]")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("YS / TS (MPa)", f"{res['ys']} / {res['ts']}")
        r2.metric("EL / RA (%)", f"{res['el']} / {res['ra']}")
        r3.metric("Hardness (HB)", f"{res['hb']}")
        r4.metric("CVN (J)", f"{res['cvn']}")
        st.info(f"**추정 조직:** {res['org']} / **결정 격자:** {res['lat']}")

with t2:
    st.header("🔄 전문가용 역설계 엔진")
    # (역설계 로직은 이전과 동일하되, p1_type과 냉각방식 선택지를 더 정밀하게 포함...)