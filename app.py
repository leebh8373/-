import streamlit as st
import pandas as pd
import numpy as np
import calculations as calc
from datetime import datetime

# Plotly 라이브러리 가용성 체크 (에러 방지용 검증 로직)
try:
    import plotly.graph_objects as go
    IS_PLOTLY_AVAILABLE = True
except ImportError:
    IS_PLOTLY_AVAILABLE = False

# [PAGE CONFIG]
st.set_page_config(page_title="Sentinel-Alpha v6.0", layout="wide")

# [CSS CUSTOM STYLE]
st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 8px; border: 1px solid #d1d5db; }
    .main-title { color: #1e3a8a; font-size: 32px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">🛡️ Sentinel-Alpha v6.0: 전문가용 전공정 시뮬레이터</p>', unsafe_allow_html=True)

# [SIDEBAR - GLOBAL PARAMETERS]
with st.sidebar:
    st.header("⚙️ 기초 공정 변수 설정")
    input_thickness = st.number_input("주물 단면 두께 (mm)", min_value=10, max_value=2500, value=150, step=10)
    input_test_temp = st.selectbox("충격 시험 온도 (℃)", [20, 0, -20, -46, -60, -101], index=3)
    st.divider()
    st.info("Pusan National Univ. Metal Materials Lab\nQuality Management Specialist System")
    st.caption(f"Build Date: {datetime.now().strftime('%Y-%m-%d')}")

# [MAIN TABS INTERFACE]
# 이미지 3번에서 보여주신 '역설계' 기능을 정식 탭으로 분리 구현했습니다.
tab_predict, tab_inverse = st.tabs(["🚀 정밀 물성 예측 시뮬레이션", "🔄 전문가용 역설계 엔진 (Inverse)"])

# --- TAB 1: 물성 예측 ---
with tab_predict:
    st.header("1️⃣ 화학 성분 정밀 설계 (20 Elements Analysis)")
    
    # 20종 원소 입력을 위한 그리드 배치 (축약 없이 전개)
    user_composition = {}
    col_row1 = st.columns(5); col_row2 = st.columns(5); col_row3 = st.columns(5); col_row4 = st.columns(5)
    
    element_list = ['C','Si','Mn','P','S','Cr','Mo','Ni','Cu','V','Nb','Ti','Al','B','N','As','Sn','Sb','Pb','Zr']
    
    for idx, element_name in enumerate(element_list):
        current_row = [col_row1, col_row2, col_row3, col_row4][idx // 5]
        default_val = 0.1850 if element_name == 'C' else 0.4500 if element_name == 'Si' else 1.4500 if element_name == 'Mn' else 0.0000
        user_composition[element_name] = current_row[idx % 5].number_input(
            f"{element_name} (%)", min_value=0.0, max_value=10.0, value=default_val, format="%.4f"
        )

    st.divider()
    st.header("2️⃣ 단계별 복합 열처리 시나리오 (1st ~ 3rd Stage)")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("📦 1차: 오스테나이트화")
        p1_type = st.selectbox("공정 종류", ["Quenching", "Normalizing", "Annealing"], key="p1_type_select")
        p1_temp = st.number_input("오스테나이트화 온도 (℃)", min_value=700, max_value=1200, value=1050, step=10, key="p1_temp_input")
        p1_time = st.number_input("가열 유지 시간 (min)", 10, 5000, 360, key="p1_time_input")
        p1_cool = st.selectbox("냉각 방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)"], key="p1_cool_select")
    
    with c2:
        st.subheader("🔥 2차: 뜨임/응력제거")
        p2_type = st.selectbox("공정 종류", ["None", "Tempering", "S/R"], index=1, key="p2_type_select")
        p2_temp = st.number_input("열처리 온도 (℃)", 0, 850, 610, key="p2_temp_input")
        p2_time = st.number_input("가열 유지 시간 (min)", 0, 5000, 240, key="p2_time_input")
        p2_cool = st.selectbox("냉각 방식", ["수냉(WQ)", "공냉(AC)", "노냉(FC)"], index=1, key="p2_cool_select")
        
    with c3:
        st.subheader("❄️ 3차: 최종 PWHT")
        p3_type = st.selectbox("공정 종류", ["None", "S/R", "PWHT"], index=1, key="p3_type_select")
        p3_temp = st.number_input("열처리 온도 (℃)", 0, 850, 625, key="p3_temp_input")
        p3_time = st.number_input("가열 유지 시간 (min)", 0, 5000, 300, key="p3_time_input")
        p3_cool = st.selectbox("냉각 방식", ["공냉(AC)", "노냉(FC)"], key="p3_cool_select")

    if st.button("📊 정밀 물성 시뮬레이션 가동", use_container_width=True):
        # 1차 물성 엔진 호출
        ts_init = calc.calculate_1st_stage_physics(user_composition, {'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool}, input_thickness)
        
        # 최종 물성 시뮬레이션 호출
        final_report = calc.get_final_expert_simulation(
            ts_init, 
            {'type':p2_type, 'temp':p2_temp, 'time':p2_t, 'cooling':p2_cool},
            {'type':p3_type, 'temp':p3_temp, 'time':p3_t, 'cooling':p3_cool},
            input_test_temp, user_composition
        )
        
        st.success("### [Sentinel-Alpha 최종 기계적 물성 예측 리포트]")
        m_cols = st.columns(5)
        m_cols[0].metric("항복강도 (YS)", f"{final_report['ys']} MPa")
        m_cols[1].metric("인장강도 (TS)", f"{final_report['ts']} MPa")
        m_cols[2].metric("연신율 (EL)", f"{final_report['el']} %")
        m_cols[3].metric("브리넬 경도 (HB)", f"{final_report['hb']}")
        m_cols[4].metric("충격치 (CVN)", f"{final_report['cvn']} J")
        
        if IS_PLOTLY_AVAILABLE:
            radar_fig = go.Figure(data=go.Scatterpolar(
                r=[final_report['ts']/10, final_report['el']*2, final_report['hb']/2, final_report['cvn']],
                theta=['TS','EL','HB','CVN'], fill='toself', name='Predicted Property'
            ))
            st.plotly_chart(radar_fig, use_container_width=True)

# --- TAB 2: 역설계 엔진 ---
with tab_inverse:
    st.header("🔄 전문가용 역설계 엔진 (Inverse Engineering)")
    st.write("목표하는 기계적 물성을 입력하면, Sentinel-Alpha가 최적의 합금 성분과 열처리 조건을 역으로 제안합니다.")
    
    ir_col1, ir_col2 = st.columns(2)
    with ir_col1:
        target_ys = st.number_input("목표 항복강도 (MPa)", 300, 1300, 485)
        target_ts = st.number_input("목표 인장강도 (MPa)", 400, 1500, 625)
    with ir_col2:
        target_cvn = st.number_input("목표 충격치 (J)", 10, 300, 65)
        
    if st.button("🔍 최적 설계 시나리오 도출", use_container_width=True):
        inverse_results = calc.run_expert_inverse_engine({
            'ys': target_ys, 'ts': target_ts, 'cvn': target_cvn,
            'test_temp': input_test_temp, 'thick': input_thickness
        })
        
        st.success("### [Sentinel-Alpha 추천 최적 설계 사양]")
        
        st.write("#### 1️⃣ 추천 성분 배합비 (Chemical Composition)")
        st.dataframe(pd.DataFrame([inverse_results['alloy']]), use_container_width=True)
        
        st.write("#### 2️⃣ 추천 열처리 공정 스케줄")
        p_list = [inverse_results['p1'], inverse_results['p2'], inverse_results['p3']]
        for idx, p in enumerate(p_list, 1):
            st.info(f"**{idx}차 공정 ({p['mode']})**: {p['temp']}℃ / {p['time']}min / 냉각: :blue[{p['cool']}]")