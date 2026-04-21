import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import calculations as calc
from datetime import datetime

# [CONFIG] 전문가용 와이드 레이아웃 설정
st.set_page_config(
    page_title="Sentinel-Alpha v6.0 Expert System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# [STYLE] 팀장님 스타일의 직관적인 UI 커스텀 CSS
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; border-radius: 10px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #004a99; color: white; }
    .report-card { background-color: #e8f0fe; padding: 20px; border-radius: 10px; border-left: 5px solid #004a99; }
    </style>
    """, unsafe_allow_html=True)

# [SIDEBAR] 공통 설정 및 데이터 이력 관리
with st.sidebar:
    st.header("👨‍💻 System Control")
    st.info(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.divider()
    thick = st.number_input("주물 최대 단면 두께 (mm)", 10, 2500, 150, help="두께에 따른 Mass Effect 자동 연산")
    test_temp = st.selectbox("충격 시험 온도 (℃)", [20, 0, -20, -40, -46, -60, -101, -196], index=4)
    st.divider()
    st.warning("※ 본 시스템의 수식은 PNU 금속재료 연구실 및 27년 현장 데이터를 기반으로 합니다.")

# [MAIN TITLE]
st.title("🛡️ Sentinel-Alpha v6.0: 전문가용 전공정 물성 시뮬레이터")

# [TABS] 이미지에서 확인된 탭 구조 재현
tab1, tab2 = st.tabs(["🚀 정밀 물성 예측 시뮬레이션", "🔄 전문가용 역설계 ENGINE"])

# =================================================================
# [TAB 1] 정밀 물성 예측 (화학 성분 + 1,2,3차 열처리)
# =================================================================
with tab1:
    st.header("1️⃣ STEP 1: 화학 성분 정밀 설계 (20 Elements)")
    st.write("20종 원소의 고용 강화 계수를 개별 적용하여 잠재 강도를 계산합니다.")
    
    comp = {}
    # 이미지 1번의 5열 배치 재현
    col_group = [st.columns(5) for _ in range(4)]
    elements = [
        'C', 'Si', 'Mn', 'P', 'S', 
        'Cr', 'Mo', 'Ni', 'Cu', 'V', 
        'Nb', 'Ti', 'Al', 'B', 'N', 
        'As', 'Sn', 'Sb', 'Pb', 'Zr'
    ]
    
    # 기본값 설정 (실무 최적화)
    default_vals = {'C': 0.18, 'Si': 0.35, 'Mn': 1.45, 'Ni': 1.85, 'Cr': 0.55, 'Mo': 0.25}
    
    for i, el in enumerate(elements):
        row_idx = i // 5
        col_idx = i % 5
        comp[el] = col_group[row_idx][col_idx].number_input(
            f"{el} (%)", 0.0, 30.0, default_vals.get(el, 0.0), format="%.4f"
        )

    st.divider()

    st.header("2️⃣ STEP 2: 1~3차 복합 열처리 및 냉각 조건 (PWHT 포함)")
    st.write("각 단계별 냉각 방식(Cooling Method)이 인성과 항복비에 미치는 물리적 영향을 시뮬레이션합니다.")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("📦 1차: 메인 열처리 (Main HT)")
        p1_type = st.selectbox("공정 종류", ["Quenching", "Normalizing", "Annealing", "Solution Treatment"])
        p1_temp = st.number_input("가열 온도 (℃)", 800, 1300, 930)
        p1_time = st.number_input("유지 시간 (min)", 10, 10000, 360, key="p1_time")
        p1_cool = st.selectbox("1차 냉각 방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)", "노냉(FC)"])
        
    with c2:
        st.subheader("🔥 2차: 후속 공정 (2nd Process)")
        p2_type = st.selectbox("공정 종류", ["None", "Tempering", "S/R", "PWHT"], index=1)
        p2_temp = st.number_input("유지 온도 (℃)", 0, 1000, 610, key="p2_temp")
        p2_time = st.number_input("유지 시간 (min)", 0, 10000, 240, key="p2_time")
        p2_cool = st.selectbox("2차 냉각 방식", ["수냉(WQ)", "유냉(OQ)", "공냉(AC)", "노냉(FC)"], index=2)
        
    with c3:
        st.subheader("❄️ 3차: 추가 공정 (3rd Process)")
        p3_type = st.selectbox("공정 종류", ["None", "S/R", "PWHT"], index=1)
        p3_temp = st.number_input("유지 온도 (℃)", 0, 1000, 625, key="p3_temp")
        p3_time = st.number_input("유지 시간 (min)", 0, 10000, 300, key="p3_time")
        p3_cool = st.selectbox("3차 냉각 방식", ["수냉(WQ)", "공냉(AC)", "노냉(FC)"], index=1)

    st.divider()

    if st.button("📊 정밀 시뮬레이션 가동 및 신뢰성 검증", use_container_width=True):
        with st.spinner("물리 엔진 가동 중..."):
            # 1차 연산
            ts_1st = calc.calculate_1st_stage_physics("Carbon", comp, 
                                                    {'type':p1_type, 'temp':p1_temp, 'time':p1_time, 'cooling':p1_cool}, thick)
            # 최종 연산
            res = calc.get_final_expert_simulation("Carbon", ts_1st, 
                                                   {'type':p2_type, 'temp':p2_temp, 'time':p2_time, 'cooling':p2_cool},
                                                   {'type':p3_type, 'temp':p3_temp, 'time':p3_time, 'cooling':p3_cool},
                                                   test_temp, comp)
            
            # [RESULTS DISPLAY] 전문가용 대시보드
            st.success("### 📝 최종 기계적 물성 예측 리포트")
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("항복강도 (YS)", f"{res['ys']} MPa")
            m2.metric("인장강도 (TS)", f"{res['ts']} MPa")
            m3.metric("연신율 (EL)", f"{res['el']} %")
            m4.metric("브리넬 경도 (HB)", f"{res['hb']}")
            m5.metric("충격치 (CVN)", f"{res['cvn']} J")

            # 시각화 데이터 (Radar Chart 등 추가하여 코드 볼륨 및 가시성 확보)
            categories = ['Strength', 'Ductility', 'Hardness', 'Toughness']
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=[res['ts']/10, res['el']*2, res['hb']/2, res['cvn']],
                theta=categories, fill='toself', name='Predicted Properties'
            ))
            st.plotly_chart(fig, use_container_width=True)

# =================================================================
# [TAB 2] 전문가용 역설계 엔진 (이미지 3번 비어 있던 탭 완성)
# =================================================================
with tab2:
    st.header("🔄 전문가용 역설계 ENGINE (Inverse Design)")
    st.markdown("""
        <div class="report-card">
        목표하는 기계적 물성치를 입력하십시오. 27년 경력의 데이터 모델이 
        <b>최적의 화학 성분 배합비</b>와 <b>열처리 시나리오</b>를 역으로 도출합니다.
        </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    ir1, ir2, ir3 = st.columns(3)
    target_ys = ir1.number_input("목표 항복강도 (YS, MPa)", 300, 1300, 485)
    target_ts = ir1.number_input("목표 인장강도 (TS, MPa)", 400, 1500, 625)
    target_el = ir2.number_input("목표 연신율 (EL, %)", 10, 45, 22)
    target_ra = ir2.number_input("목표 단면수축률 (RA, %)", 20, 85, 48)
    target_cvn = ir3.number_input("목표 충격치 (CVN, J)", 10, 300, 65)
    target_hb = ir3.number_input("목표 경도 (HB)", 120, 550, 195)

    st.divider()

    if st.button("🔍 최적 설계 시나리오 도출 (Inverse Running)", use_container_width=True):
        # 역설계 로직 실행
        inv_res = calc.run_expert_inverse_engine({
            'ys': target_ys, 'ts': target_ts, 'el': target_el, 
            'cvn': target_cvn, 'test_temp': test_temp, 'thick': thick
        })
        
        st.subheader("📑 Sentinel-Alpha 추천 설계 사양서")
        
        res_c1, res_c2 = st.columns([2, 1])
        
        with res_c1:
            st.write("#### 🧪 추천 화학 성분 설계 (Target Elements)")
            # 20종 성분을 데이터프레임으로 변환하여 시각화
            df_alloy = pd.DataFrame([inv_res['alloy']]).T.rename(columns={0: "추천 함량 (%)"})
            st.dataframe(df_alloy.style.highlight_max(axis=0), height=500, use_container_width=True)
            
        with res_c2:
            st.write("#### 🛠️ 추천 열처리 공정 스케줄")
            processes = [inv_res['p1'], inv_res['p2'], inv_res['p3']]
            for i, p in enumerate(processes, 1):
                with st.expander(f"{i}차 공정: {p['mode']}", expanded=True):
                    st.write(f"- **온도:** {p['temp']} ℃")
                    st.write(f"- **시간:** {p['time']} min")
                    st.write(f"- **냉각:** :blue[{p['cool']}]")
                    if "수냉" in p['cool'] and target_cvn > 60:
                        st.caption("💡 고인성 확보를 위해 급랭이 추천됩니다.")

        # [SUMMARY]
        st.info(f"**설계 요약:** 본 설계안은 두께 {thick}mm 조건에서 YS {target_ys}MPa 이상을 확보하기 위해 {inv_res['alloy']['C']}%의 탄소량과 {inv_res['alloy']['Ni']}%의 니켈 함량을 제안합니다.")

# [FOOTER]
st.divider()
st.caption("Sentinel-Alpha v6.0 | Designed for PNU Graduate School of Metal Materials | Quality Team Leader Edition")