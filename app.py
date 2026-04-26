import streamlit as st
import pandas as pd
import numpy as np
import calculations as calc
from datetime import datetime

__version__ = "6.1.0" # Professional Upgrade Version

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
    .stMetric { background-color: #1e293b; padding: 15px; border-radius: 10px; border: 1px solid #334155; color: white; }
    .stMetric label { color: #94a3b8 !important; font-weight: bold; }
    .stMetric [data-testid="stMetricValue"] { color: #ffffff !important; font-weight: 800; }
    .main-title { color: #1e3a8a; font-size: 32px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">🛡️ Sentinel-Alpha v6.0: 전문가용 전공정 시뮬레이터</p>', unsafe_allow_html=True)

# [SIDEBAR - GLOBAL PARAMETERS]
with st.sidebar:
    st.header("⚙️ 기초 공정 변수 설정")
    input_thickness = st.number_input("주물 단면 두께 (mm)", min_value=10, max_value=2500, value=150, step=10)
    input_test_temp = st.selectbox("충격 시험 온도 (℃)", [20, 0, -20, -46, -60, -101], index=3)
    ceq_standard = st.selectbox("Ceq/Pcm 계산 규격", ["IIW (ASTM/ASME/EN)", "JIS", "Pcm (API/NORSOK)", "CET (European)"])
    st.divider()
    st.info("Pusan National Univ. Metal Materials Lab\nQuality Management Specialist System")
    st.caption(f"Build Date: {datetime.now().strftime('%Y-%m-%d')}")

# [MAIN TABS INTERFACE]
tab_predict, tab_inverse = st.tabs(["🚀 정밀 물성 예측 시뮬레이션", "🔄 전문가용 역설계 엔진 (Inverse)"])

# --- TAB 1: 물성 예측 ---
with tab_predict:
    st.header("1️⃣ 화학 성분 정밀 설계 (20 Elements Analysis)")
    
    # 20종 원소 입력을 위한 그리드 배치
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
        ts_init = calc.calculate_1st_stage_physics(user_composition, {'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool}, input_thickness)
        # 최종 물성 시뮬레이션 호출 (v6 캐시 갱신 버전)
        try:
            final_report = calc.run_simulation_v6(
                ts_1st=ts_init, 
                p2={'type':p2_type, 'temp':p2_temp, 'time':p2_time, 'cooling':p2_cool},
                p3={'type':p3_type, 'temp':p3_temp, 'time':p3_time, 'cooling':p3_cool},
                test_temp=input_test_temp, 
                comp=user_composition,
                p1={'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool},
                thickness=input_thickness,
                ceq_standard=ceq_standard
            )
        except TypeError as e:
            st.error(f"⚠️ 시뮬레이션 엔진 호출 오류 (TypeError): {e}")
            st.info("임시 해결책: 페이지를 새로고침(F5)하거나 관리자에게 문의하세요.")
            st.stop()
        except Exception as e:
            st.error(f"⚠️ 시뮬레이션 실행 중 예상치 못한 오류 발생: {e}")
            st.stop()
        
        st.success("### [Sentinel-Alpha 최종 기계적 물성 예측 리포트]")
        m_cols1 = st.columns(3)
        m_cols1[0].metric("항복강도 (YS)", f"{final_report['ys']} MPa")
        m_cols1[1].metric("인장강도 (TS)", f"{final_report['ts']} MPa")
        m_cols1[2].metric("브리넬 경도 (HB)", f"{final_report['hb']}")
        
        m_cols2 = st.columns(3)
        m_cols2[0].metric("연신율 (EL)", f"{final_report['el']} %")
        m_cols2[1].metric("단면수축률 (RA)", f"{final_report['ra']} %")
        m_cols2[2].metric("충격치 (CVN)", f"{final_report['cvn']} J")

        st.divider()
        st.subheader("🧪 화학적/야금학적 특성 (Chemical & Metallurgical)")
        t_cols = st.columns(2)
        t_cols[0].metric(f"{final_report['ceq_label']}", f"{final_report['ceq_val']}")
        t_cols[1].info(f"**적용 규격:** {ceq_standard}")

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
        
        thickness_range = np.linspace(10, 1000, 50)
        sim_results = []
        for t in thickness_range:
            ts_1st = calc.calculate_1st_stage_physics(user_composition, {'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool}, t)
            rep = calc.get_final_expert_simulation(ts_1st, {'type':p2_type, 'temp':p2_temp, 'time':p2_time, 'cooling':p2_cool}, {'type':p3_type, 'temp':p3_temp, 'time':p3_time, 'cooling':p3_cool}, input_test_temp, user_composition)
            sim_results.append({'Thickness': t, 'YS': rep['ys'], 'TS': rep['ts']})
        
        sim_df = pd.DataFrame(sim_results)
        
        if IS_PLOTLY_AVAILABLE:
            fig_sens = go.Figure()
            fig_sens.add_trace(go.Scatter(x=sim_df['Thickness'], y=sim_df['TS'], name='인장강도 (TS)', line=dict(color='#ef4444', width=3)))
            fig_sens.add_trace(go.Scatter(x=sim_df['Thickness'], y=sim_df['YS'], name='항복강도 (YS)', line=dict(color='#3b82f6', width=3, dash='dash')))
            fig_sens.update_layout(
                title="두께 증가에 따른 강도 저하 시뮬레이션",
                xaxis_title="두께 (mm)", yaxis_title="강도 (MPa)",
                hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            # 현재 두께 위치 표시
            fig_sens.add_vline(x=input_thickness, line_dash="dot", line_color="green", annotation_text=f"현재 설정: {input_thickness}mm")
            st.plotly_chart(fig_sens, use_container_width=True)
        else:
            st.line_chart(sim_df.set_index('Thickness'))
        
        st.info("💡 **전문가 팁**: 그래프의 기울기가 급격히 변하는 지점이 해당 합금의 유효 경화 깊이 한계입니다. 대형재의 경우 Mo, Cr 함량을 높여 그래프를 완만하게 만들어야 합니다.")

# --- TAB 2: 역설계 엔진 ---
with tab_inverse:
    st.header("🔄 전문가용 역설계 엔진 (Inverse Engineering)")
    st.write("목표하는 기계적 물성을 입력하면, Sentinel-Alpha가 최적의 합금 성분과 열처리 조건을 역으로 제안합니다.")
    
    ir_col1, ir_col2 = st.columns(2)
    with ir_col1:
        st.subheader("🎯 목표 기계적 성질 (Targets)")
        target_ys = st.number_input("목표 항복강도 (MPa)", 300, 1300, 485)
        target_ts = st.number_input("목표 인장강도 (MPa)", 400, 1500, 625)
        target_el = st.number_input("목표 연신율 (%)", 5, 50, 22)
        target_ra = st.number_input("목표 단면수축률 (%)", 10, 80, 45)
        target_hb = st.number_input("목표 경도 (HB)", 100, 500, 210)
        target_cvn = st.number_input("목표 충격치 (J)", 10, 300, 65)
        
    with ir_col2:
        st.subheader("🛠️ 설계 제약 조건 (Constraints)")
        target_p1_temp = st.number_input("1차 오스테나이트화 온도 (℃)", 700, 1200, 1050)
        st.info("※ 1차 열처리 온도를 고정값으로 설정하여 합금 성분을 역설계합니다.")
        
    if st.button("🔍 최적 설계 시나리오 도출", use_container_width=True):
        inverse_results = calc.run_inverse_v6(targets={
            'ys': target_ys, 'ts': target_ts, 'cvn': target_cvn,
            'el': target_el, 'ra': target_ra, 'hb': target_hb,
            'p1_temp': target_p1_temp,
            'test_temp': input_test_temp, 'thick': input_thickness,
            'ceq_standard': ceq_standard
        })
        
        st.success("### [Sentinel-Alpha 추천 최적 설계 사양]")
        
        # 전문가 분석 코멘트 추가
        if inverse_results.get('comments'):
            with st.expander("🧐 전문가 분석 의견 (Technical Insights)", expanded=True):
                for comment in inverse_results['comments']:
                    st.write(f"- {comment}")
                st.info(f"**{inverse_results['ceq_label']}:** {inverse_results['ceq_val']} (규격: {ceq_standard})")

        st.write("#### 1️⃣ 추천 성분 배합비 (Chemical Composition)")
        st.dataframe(pd.DataFrame([inverse_results['alloy']]), use_container_width=True)
        
        st.write("#### 2️⃣ 추천 열처리 공정 스케줄")
        p_list = [inverse_results['p1'], inverse_results['p2'], inverse_results['p3']]
        for idx, p in enumerate(p_list, 1):
            st.info(f"**{idx}차 공정 ({p['mode']})**: {p['temp']}℃ / {p['time']}min / 냉각: :blue[{p['cool']}]")