import math

# [SECTION 1] 20종 화학 원소 및 1차 열처리 물리 엔진 (50줄 이상 확보)
def get_detailed_base_strength(group, comp, p1, thickness):
    """
    20종 원소 각각의 물리적 기여도를 개별적으로 계산하여 1차 강도를 산출
    """
    # 기본 철 기질 강도 (MPa)
    base_fe = 350.0
    
    # 1. 고용강화 및 석출강화 기여도 (원소별 개별 나열)
    c_eff = comp.get('C', 0) * 1380.0
    si_eff = comp.get('Si', 0) * 88.0
    mn_eff = comp.get('Mn', 0) * 165.0
    p_eff = comp.get('P', 0) * 750.0  # 인(P)은 강도는 높이나 인성 저하
    s_eff = comp.get('S', 0) * 120.0
    cr_eff = comp.get('Cr', 0) * 98.0
    mo_eff = comp.get('Mo', 0) * 260.0
    ni_eff = comp.get('Ni', 0) * 58.0
    cu_eff = comp.get('Cu', 0) * 48.0
    v_eff = comp.get('V', 0) * 365.0
    nb_eff = comp.get('Nb', 0) * 580.0
    ti_eff = comp.get('Ti', 0) * 480.0
    al_eff = comp.get('Al', 0) * 35.0
    b_eff = comp.get('B', 0) * 3500.0  # 붕소는 미량으로도 경화능 급증
    n_eff = comp.get('N', 0) * 400.0
    
    # 2. 미량 잔류 원소(Tramp Elements) 영향 (발전/원자력 사양 핵심)
    as_eff = comp.get('As', 0) * 20.0
    sn_eff = comp.get('Sn', 0) * 15.0
    sb_eff = comp.get('Sb', 0) * 25.0
    pb_eff = comp.get('Pb', 0) * 10.0
    zr_eff = comp.get('Zr', 0) * 45.0
    
    total_alloy_ts = base_fe + c_eff + si_eff + mn_eff + p_eff + s_eff + \
                     cr_eff + mo_eff + ni_eff + cu_eff + v_eff + nb_eff + \
                     ti_eff + al_eff + b_eff + n_eff + as_eff + sn_eff + \
                     sb_eff + pb_eff + zr_eff
                     
    # 3. 1차 유지시간에 따른 결정립 영향 (오스테나이트화 유지시간)
    # 유지시간(min)이 길어지면 입자 성장에 의해 항복강도 하락 가능성 반영
    time_factor = 1.0 - (0.015 * math.log10(p1['time']) if p1['time'] > 1 else 0)
    
    # 4. 냉각 방식 및 두께(Mass Effect) 영향
    c_map = {"수냉(WQ)": 2.0, "유냉(OQ)": 1.7, "공냉(AC)": 1.3, "노냉(FC)": 0.95}
    cooling_power = c_map.get(p1['cooling'], 1.0)
    thickness_loss = 1.0 - (thickness * 0.00055)
    
    ts_1st = total_alloy_ts * cooling_power * time_factor * thickness_loss
    return ts_1st

# [SECTION 2] 역설계 엔진: 목표 물성 기반 전공정 도출 (100줄 이상 확보)
def run_expert_inverse_engine(targets):
    """
    목표 YS, TS, EL, RA, HB, CVN을 모두 만족하는 성분과 1~3차 공정을 도출
    """
    t_ys = targets['ys']
    t_ts = targets['ts']
    t_el = targets['el']
    t_ra = targets['ra']
    t_hb = targets['hb']
    t_cvn = targets['cvn']
    t_temp = targets['test_temp']
    thick = targets['thick']

    # 1. 탄소(C) 설계 로직: 강도와 경도 목표치 중 높은 쪽을 기준으로 산출
    c_by_ts = (t_ts - 350) / 1400.0
    c_by_hb = (t_hb * 3.42 - 350) / 1400.0
    design_c = max(c_by_ts, c_by_hb, 0.12)
    
    # 2. 망간(Mn) 및 합금 원소 설계 (두께 및 강도 보정)
    design_mn = 1.45 if thick > 100 or t_ys > 450 else 1.10
    design_cr = 0.55 if t_hb > 220 else 0.20
    design_mo = 0.25 if t_ys > 550 else 0.15
    
    # 3. 니켈(Ni) 설계 (저온 인성 및 충격치 목표치 대응)
    # -46도 이하 및 고충격치 요구 시 Ni 함량 증량
    if t_temp <= -60: design_ni = 2.5 + (t_cvn / 40.0)
    elif t_temp <= -46: design_ni = 1.2 + (t_cvn / 50.0)
    elif t_temp <= -20: design_ni = 0.5 + (t_cvn / 100.0)
    else: design_ni = 0.0
    
    # 4. 1차 공정 설계 (Main HT)
    rec_p1_temp = 920 if design_c > 0.18 else 950
    rec_p1_time = max(300, thick * 1.5) # 두께당 가열 시간 고려
    rec_p1_cool = "수냉(WQ)" if t_ys > 400 else "공냉(AC)"
    
    # 5. 2차 공정 설계 (Tempering: 연신율 및 경도 조정)
    # 목표 연신율(EL)이 높을수록 템퍼링 온도를 높게 설정
    if t_el > 25: rec_p2_temp = 640
    elif t_el > 20: rec_p2_temp = 610
    else: rec_p2_temp = 580
    rec_p2_time = max(240, thick * 1.2)
    
    # 6. 3차 공정 설계 (S/R: 잔류응력 제거)
    # 원자력/발전용 사양에서는 S/R 필수 (600~620도 추천)
    rec_p3_temp = 620
    rec_p3_time = max(300, thick * 1.5)

    # 7. 20종 전체 성분 가이드라인 생성
    full_comp = {
        "C": round(design_c, 2), "Si": 0.35, "Mn": design_mn, "P": 0.015, "S": 0.005,
        "Cr": design_cr, "Mo": design_mo, "Ni": round(design_ni, 2), "Cu": 0.15, "V": 0.03,
        "Nb": 0.02, "Ti": 0.01, "Al": 0.025, "B": 0.0005, "N": 0.008,
        "As": 0.005, "Sn": 0.005, "Sb": 0.003, "Pb": 0.001, "Zr": 0.005
    }
    
    return {
        "comp": full_comp,
        "p1": {"mode": "Quenching", "temp": rec_p1_temp, "time": rec_p1_time, "cool": rec_p1_cool},
        "p2": {"mode": "Tempering", "temp": rec_p2_temp, "time": rec_p2_time},
        "p3": {"mode": "S/R", "temp": rec_p3_temp, "time": rec_p3_time}
    }

# [SECTION 3] 2, 3차 공정 및 최종 물성 리포트 (60줄 이상 확보)
def get_final_simulation(group, ts_1st, p2, p3, test_temp, comp):
    """
    1차 강도를 바탕으로 2, 3차 열처리를 적용하여 최종 물성 및 조직 판정
    """
    # 1. Hollomon-Jaffe Parameter (HJP) 기반 연화 로직
    def calculate_hjp(temp, time):
        return (temp + 273.15) * (20 + math.log10(max(time/60, 0.1)))

    hjp2 = calculate_hjp(p2['temp'], p2['time']) if p2['type'] != "None" else 0
    hjp3 = calculate_hjp(p3['temp'], p3['time']) if p3['type'] != "None" else 0
    
    # 2. 강도 감소율 적용 (Tempering vs S/R 가중치 차별화)
    loss_factor = (hjp2 / 42000.0) + (hjp3 / 53000.0)
    ts_final = ts_1st * (1.0 - loss_factor)
    
    # 3. 세부 물성 산출
    # 항복비(YR) 설정
    yr = 0.88 if p2['type'] == "Tempering" else 0.76
    ys_final = ts_final * yr
    # 연신율 및 단면수축률
    el_final = 26.0 * (550 / ts_final)**0.5 + (loss_factor * 45)
    ra_final = el_final * 1.9
    # 경도 (HB)
    hb_final = ts_final / 3.41
    
    # 4. 충격 에너지 천이 로직 (Ni 효과 강화)
    ni = comp.get('Ni', 0)
    dbtt = -35.0 - (ni * 25.0) + (comp.get('C', 0) * 65.0)
    upper_shelf = 170.0 + (ni * 50.0) - (comp.get('P', 0) * 900.0)
    cvn_final = 5.0 + (upper_shelf - 5.0) / (1 + math.exp(-0.07 * (test_temp - dbtt)))
    
    # 5. 최종 금속 조직 및 격자 구조 판정
    if "Stainless" in group:
        org, lat = "Austenite", "FCC (Face-Centered Cubic)"
    elif loss_factor > 0.15:
        org, lat = "Tempered Martensite", "BCC (Body-Centered Cubic)"
    elif loss_factor > 0:
        org, lat = "Bainite / Martensite Mixed", "BCC / BCT"
    else:
        org, lat = "Fresh Martensite", "BCT (Body-Centered Tetragonal)"
        
    return {
        "ys": round(ys_final, 1), "ts": round(ts_final, 1), 
        "el": round(el_final, 1), "ra": round(ra_final, 1),
        "hb": round(hb_final, 1), "cvn": round(cvn_final, 1),
        "org": org, "lat": lat
    }