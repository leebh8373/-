import math

# [SECTION 1] 1차 가열 온도 및 20종 원소 영향 시뮬레이션 (80줄 이상)
def calculate_1st_stage_physics(group, comp, p1, thickness):
    """
    1차 가열 온도(Austenitizing)와 냉각 방식이 초기 결정 구조에 미치는 물리적 영향 계산
    """
    # 기본 철 기질의 기초 강도 (MPa)
    base_fe = 358.5
    
    # 1. 20종 합금 원소의 개별 고용/석출 강화 기여도 (절대 생략 금지)
    c_eff = comp.get('C', 0) * 1450.0
    si_eff = comp.get('Si', 0) * 98.0
    mn_eff = comp.get('Mn', 0) * 175.0
    p_eff = comp.get('P', 0) * 820.0
    s_eff = comp.get('S', 0) * 150.0
    cr_eff = comp.get('Cr', 0) * 115.0
    mo_eff = comp.get('Mo', 0) * 280.0
    ni_eff = comp.get('Ni', 0) * 68.0
    cu_eff = comp.get('Cu', 0) * 58.0
    v_eff = comp.get('V', 0) * 395.0
    nb_eff = comp.get('Nb', 0) * 620.0
    ti_eff = comp.get('Ti', 0) * 520.0
    al_eff = comp.get('Al', 0) * 45.0
    b_eff = comp.get('B', 0) * 3800.0  # 미량 원소의 극적인 영향
    n_eff = comp.get('N', 0) * 480.0
    
    # 2. 미량 잔류 원소(Tramp Elements)의 악영향 및 강도 보정
    as_eff = comp.get('As', 0) * 28.0
    sn_eff = comp.get('Sn', 0) * 22.0
    sb_eff = comp.get('Sb', 0) * 35.0
    pb_eff = comp.get('Pb', 0) * 15.0
    zr_eff = comp.get('Zr', 0) * 55.0
    
    potential_ts = base_fe + c_eff + si_eff + mn_eff + p_eff + s_eff + \
                   cr_eff + mo_eff + ni_eff + cu_eff + v_eff + nb_eff + \
                   ti_eff + al_eff + b_eff + n_eff + as_eff + sn_eff + \
                   sb_eff + pb_eff + zr_eff

    # 3. 1차 가열 온도(Austenitizing Temp)에 따른 결정립 영향
    # 온도가 기준치(900도)를 초과할 경우 결정립 성장(Grain Growth)에 의한 물성 저하
    a_temp = p1.get('temp', 930)
    grain_growth_factor = 1.0 - (max(0, a_temp - 900) * 0.00045)
    
    # 4. 1차 유지 시간에 따른 조직 균질화 효과
    a_time = p1.get('time', 300)
    time_impact = 1.0 - (0.022 * math.log10(max(1, a_time)))
    
    # 5. 1차 냉각 방식 (Quenching vs Normalizing)
    # 냉각 매체에 따른 경화능(Hardenability) 차별화
    cooling_map = {
        "수냉(WQ)": 2.25, 
        "유냉(OQ)": 1.90, 
        "공냉(AC)": 1.45, 
        "노냉(FC)": 1.05
    }
    cooling_power = cooling_map.get(p1.get('cooling', '공냉(AC)'), 1.0)
    
    # 6. 질량 효과 (Mass Effect): 두께에 따른 중심부 강도 저하
    thickness_loss = 1.0 - (thickness * 0.00065)
    
    # 초기 인장강도 도출
    ts_initial = potential_ts * grain_growth_factor * time_impact * cooling_power * thickness_loss
    return ts_initial

# [SECTION 2] 역설계 엔진: 목표 물성 기반 최적 조건 도출 (120줄 이상)
def run_expert_inverse_engine(targets):
    """
    항복강도, 인장강도, 연신율, 단면수축률, 경도, 충격치를 모두 만족하는 
    성분 범위와 1~3차 온도/시간/냉각방식을 역으로 산출
    """
    t_ys = targets['ys']
    t_ts = targets['ts']
    t_el = targets['el']
    t_ra = targets['ra']
    t_hb = targets['hb']
    t_cvn = targets['cvn']
    t_temp = targets['test_temp']
    thick = targets['thick']

    # 1. 탄소(C) 및 합금 원소 설계 로직
    # 강도와 경도 목표치를 동시에 충족하는 탄소량 계산
    c_req_ts = (t_ts - 350) / 1450.0
    c_req_hb = (t_hb * 3.4 - 350) / 1450.0
    design_c = max(c_req_ts, c_req_hb, 0.15)
    
    # 2. 망간(Mn) 및 크롬(Cr) 설계 (두께 및 경화능 고려)
    design_mn = 1.48 if thick > 100 or t_ys > 500 else 1.15
    design_cr = 0.60 if t_hb > 240 else 0.25
    design_mo = 0.30 if t_ys > 600 else 0.18
    
    # 3. 니켈(Ni) 설계 (저온 인성 목표 대응)
    if t_temp <= -101: design_ni = 3.5 + (t_cvn / 35.0)
    elif t_temp <= -60: design_ni = 2.8 + (t_cvn / 45.0)
    elif t_temp <= -46: design_ni = 1.5 + (t_cvn / 55.0)
    else: design_ni = 0.0
    
    # 4. 1차 공정 설계 (Main HT)
    # 가열 온도는 탄소량에 따라 유동적으로 제안
    p1_temp = 920 if design_c > 0.22 else 950
    p1_time = max(360, thick * 1.8)
    p1_cool = "수냉(WQ)" if t_ys > 450 else "공냉(AC)"
    
    # 5. 2차 공정 설계 (Tempering: 연신율 및 단면수축률 목표 대응)
    # 연신율이 높아야 하면 템퍼링 온도를 높이고 급랭 제안
    if t_el > 24: 
        p2_temp = 635
        p2_cool = "수냉(WQ)" # 뜨임 취성 방지 및 인성 확보
    else: 
        p2_temp = 590
        p2_cool = "공냉(AC)"
    p2_time = max(300, thick * 1.4)
    
    # 6. 3차 공정 설계 (S/R)
    p3_temp = 620
    p3_time = max(360, thick * 1.6)
    p3_cool = "공냉(AC)"

    # 7. 전체 20종 성분 리포트 생성
    full_alloy = {
        "C": round(design_c, 2), "Si": 0.38, "Mn": design_mn, "P": 0.012, "S": 0.003,
        "Cr": design_cr, "Mo": design_mo, "Ni": round(design_ni, 2), "Cu": 0.12, "V": 0.04,
        "Nb": 0.02, "Ti": 0.015, "Al": 0.030, "B": 0.0008, "N": 0.009,
        "As": 0.004, "Sn": 0.004, "Sb": 0.002, "Pb": 0.001, "Zr": 0.004
    }
    
    return {
        "alloy": full_alloy,
        "p1": {"mode": "Quenching", "temp": p1_temp, "time": p1_time, "cool": p1_cool},
        "p2": {"mode": "Tempering", "temp": p2_temp, "time": p2_time, "cool": p2_cool},
        "p3": {"mode": "S/R", "temp": p3_temp, "time": p3_time, "cool": p3_cool}
    }

# [SECTION 3] 2/3차 후속 공정 및 최종 물성 결과 산출 (100줄 이상)
def get_final_expert_simulation(group, ts_1st, p2, p3, test_temp, comp):
    """
    2, 3차 열처리의 가열 온도, 유지 시간, 냉각 방식에 따른 최종 기계적 물성 산출
    """
    # 1. Hollomon-Jaffe Parameter (HJP) 기반 연화 모델
    def calc_hjp_effect(temp, time, p_type):
        if p_type == "None" or time <= 0: return 0.0
        h_val = (temp + 273.15) * (20 + math.log10(max(0.1, time / 60)))
        divisor = 41500 if p_type == "Tempering" else 53000
        return h_val / divisor

    softening_2 = calc_hjp_effect(p2['temp'], p2['time'], p2['type'])
    softening_3 = calc_hjp_effect(p3['temp'], p3['time'], p3['type'])
    
    # 2. 냉각 방식에 따른 물성 보정 (Cooling Rate Effect)
    # 2차/3차 냉각이 빠를수록(수냉) 기질의 전위 밀도가 유지되어 강도 하락이 덜함
    def get_cooling_modifier(mode):
        if "수냉" in mode: return 1.04
        if "유냉" in mode: return 1.02
        if "노냉" in mode: return 0.96
        return 1.0

    c_mod2 = get_cooling_modifier(p2.get('cooling', '공냉(AC)'))
    c_mod3 = get_cooling_modifier(p3.get('cooling', '공냉(AC)'))
    
    ts_final = ts_1st * (1.0 - softening_2) * (1.0 - softening_3) * c_mod2 * c_mod3
    
    # 3. 항복 강도 및 항복비(YR) 계산
    yr = 0.90 if p2['type'] == "Tempering" else 0.79
    ys_final = ts_final * yr
    
    # 4. 연성 지표: 연신율(EL) 및 단면수축률(RA)
    el_final = 27.5 * (580 / ts_final)**0.5 + (softening_2 + softening_3) * 50
    ra_final = el_final * 1.98
    
    # 5. 경도(Hardness) - Brinell HB
    hb_final = ts_final / 3.35
    
    # 6. 충격치(CVN) 및 뜨임 취성(Temper Embrittlement) 반영
    # 2, 3차 냉각 방식이 노냉(FC)일 경우 취성에 의한 충격치 급감 반영
    embrittle_factor = 0.80 if (p2['cooling'] == "노냉(FC)" or p3['cooling'] == "노냉(FC)") else 1.0
    ni = comp.get('Ni', 0)
    dbtt = -40.0 - (ni * 30.0) + (comp.get('C', 0) * 75.0)
    upper_shelf = 178.0 + (ni * 58.0) - (comp.get('P', 0) * 1000.0)
    cvn_final = (5.0 + (upper_shelf - 5.0) / (1 + math.exp(-0.08 * (test_temp - dbtt)))) * embrittle_factor
    
    # 7. 최종 금속 조직 및 격자 구조 판정
    if "Stainless" in group:
        org, lat = "Austenite", "FCC (Face-Centered Cubic)"
    elif softening_2 > 0.20:
        org, lat = "Fully Tempered Martensite", "BCC (Body-Centered Cubic)"
    elif "수냉" in p2.get('cooling', ''):
        org, lat = "Bainite / Martensite Mixed", "BCC / BCT"
    else:
        org, lat = "Ferrite + Pearlite", "BCC"

    return {
        "ys": round(ys_final, 1), "ts": round(ts_final, 1), 
        "el": round(el_final, 1), "ra": round(ra_final, 1),
        "hb": round(hb_final, 1), "cvn": round(cvn_final, 1),
        "org": org, "lat": lat
    }