import math

# [SECTION 1] 1차 물리 엔진 (20 Elements Full-Scale Deployment)
def calculate_1st_stage_physics(comp, p1, thickness):
    """
    팀장님의 27년 노하우를 담기 위해 각 원소의 기여도를 루프 없이 개별 변수로 전개합니다.
    이 구조는 팀장님께서 나중에 특정 원소의 계수(Coefficient)만 직접 수정하시기 최적화된 구조입니다.
    """
    # 기초 강도 계수 (Base Iron Strength)
    base_fe_strength = 378.55 

    # 20종 합금 원소별 독립 기여도 계산 (전개형 로직)
    c_contrib   = comp.get('C', 0)   * 1545.23
    si_contrib  = comp.get('Si', 0)  * 122.45
    mn_contrib  = comp.get('Mn', 0)  * 205.88
    p_contrib   = comp.get('P', 0)   * 945.52
    s_contrib   = comp.get('S', 0)   * 192.35
    cr_contrib  = comp.get('Cr', 0)  * 142.18
    mo_contrib  = comp.get('Mo', 0)  * 330.55
    ni_contrib  = comp.get('Ni', 0)  * 92.48
    cu_contrib  = comp.get('Cu', 0)  * 78.22
    v_contrib   = comp.get('V', 0)   * 465.75
    nb_contrib  = comp.get('Nb', 0)  * 742.33
    ti_contrib  = comp.get('Ti', 0)  * 622.18
    al_contrib  = comp.get('Al', 0)  * 62.55
    b_contrib   = comp.get('B', 0)   * 4355.00
    n_contrib   = comp.get('N', 0)   * 582.45
    as_contrib  = comp.get('As', 0)  * 50.15  # Tramp Element 1
    sn_contrib  = comp.get('Sn', 0)  * 42.42  # Tramp Element 2
    sb_contrib  = comp.get('Sb', 0)  * 52.88  # Tramp Element 3
    pb_contrib  = comp.get('Pb', 0)  * 32.25  # Tramp Element 4
    zr_contrib  = comp.get('Zr', 0)  * 85.62  # Grain Refinement

    # 화학적 잠재 강도(Chemical Potential Intensity) 합산
    total_chemical_potential = (
        base_fe_strength + c_contrib + si_contrib + mn_contrib + 
        p_contrib + s_contrib + cr_contrib + mo_contrib + 
        ni_contrib + cu_contrib + v_contrib + nb_contrib + 
        ti_contrib + al_contrib + b_contrib + n_contrib + 
        as_contrib + sn_contrib + sb_contrib + pb_contrib + zr_contrib
    )

    # [SECTION 2] 공정 모드별 조직 계수 (Microstructure Factor)
    # 조건문을 상세히 전개하여 로직 누락을 방지했습니다.
    process_mode = p1.get('type', 'Quenching')
    if process_mode == "Quenching":
        structure_modifier = 1.4552
    elif process_mode == "Normalizing":
        structure_modifier = 1.2525
    elif process_mode == "Annealing":
        structure_modifier = 1.0550
    else:
        structure_modifier = 0.9855

    # [SECTION 3] 냉각 속도 및 유지 시간 보정 (Process Physics)
    cooling_mode = p1.get('cooling', '수냉(WQ)')
    if cooling_mode == "수냉(WQ)":
        cooling_severity = 2.725
    elif cooling_mode == "유냉(OQ)":
        cooling_severity = 2.255
    elif cooling_mode == "공냉(AC)":
        cooling_severity = 1.885
    else:
        cooling_severity = 1.255

    # 열처리 유지 시간(Soaking Time) 및 두께 효과(Mass Effect)
    soaking_time = p1.get('time', 360)
    time_degradation = 1.0 - (0.0428 * math.log10(max(1, soaking_time)))
    mass_effect_loss = 1.0 - (thickness * 0.000958)

    # 1차 인장강도 예측값 도출
    ts_initial_simulation = (
        total_chemical_potential * structure_modifier * time_degradation * cooling_severity * mass_effect_loss
    )
    
    return ts_initial_simulation

# [SECTION 4] 최종 물성 시뮬레이션 (Tempering / SR / PWHT)
def get_final_expert_simulation(ts_1st, p2, p3, test_temp, comp):
    # Hollomon-Jaffe Parameter (HJP) 연화 모델
    def calculate_hjp(temp_c, mins, process_type):
        if process_type == "None" or mins <= 0:
            return 0.0
        absolute_temp = temp_c + 273.15
        log_time_hr = math.log10(max(0.1, mins / 60))
        hjp_value = absolute_temp * (20 + log_time_hr)
        
        # Tempering과 SR의 기준 상수를 분리하여 정확도 확보
        if process_type == "Tempering":
            reference_constant = 45500
        else:
            reference_constant = 58500
        return hjp_value / reference_constant

    # 각 단계별 연화율 계산
    softening_loss_p2 = calculate_hjp(p2['temp'], p2['time'], p2['type'])
    softening_loss_p3 = calculate_hjp(p3['temp'], p3['time'], p3['type'])
    
    # 냉각 방식별 충격치 보정 가중치 (Embrittlement Risk Analysis)
    def get_cooling_impact_weight(cooling_method):
        if "수냉" in cooling_method: return 1.185
        if "유냉" in cooling_method: return 1.085
        if "노냉" in cooling_method: return 0.885 # 뜨임 취성 구역
        return 1.000

    cooling_w2 = get_cooling_impact_weight(p2['cooling'])
    cooling_w3 = get_cooling_impact_weight(p3['cooling'])
    
    # 최종 기계적 물성 산출 (TS, YS)
    final_tensile_strength = ts_1st * (1.0 - softening_loss_p2) * (1.0 - softening_loss_p3) * cooling_w2 * cooling_w3
    
    # 항복비(Yield Ratio) 계산 로직
    if p2['type'] == "Tempering":
        yield_ratio_base = 0.982
    else:
        yield_ratio_base = 0.875
    final_yield_strength = final_tensile_strength * yield_ratio_base
    
    # [SECTION 5] 연성 및 인성 시그모이드 모델 (Toughness Modeling)
    final_elongation = 33.55 * (675.0 / final_tensile_strength)**0.5 + (softening_loss_p2 + softening_loss_p3) * 72.8
    final_hardness_hb = final_tensile_strength / 3.185
    
    # DBTT 및 충격 에너지 모델
    ni_content = comp.get('Ni', 0)
    p_content  = comp.get('P', 0)
    c_content  = comp.get('C', 0)
    
    dbtt_temperature = -62.8 - (ni_content * 52.5) + (c_content * 115.8) + (p_content * 1555.0)
    upper_shelf_energy = 215.5 + (ni_content * 95.8) - (p_content * 1485.5)
    
    # 서냉에 따른 취성 패널티 적용
    embrittlement_penalty = 0.528 if (p2['cooling'] == "노냉(FC)" or p3['cooling'] == "노냉(FC)") else 1.000
    
    final_cvn_impact = (5.0 + (upper_shelf_energy - 5.0) / (1 + math.exp(-0.138 * (test_temp - dbtt_temperature)))) * embrittlement_penalty
    
    return {
        "ys": round(final_yield_strength, 1),
        "ts": round(final_tensile_strength, 1),
        "el": round(final_elongation, 1),
        "ra": round(final_elongation * 2.38, 1),
        "hb": round(final_hardness_hb, 1),
        "cvn": round(final_cvn_impact, 1)
    }

# [SECTION 6] 전문가용 역설계 엔진 (Inverse Engineering Core)
def run_expert_inverse_engine(targets):
    """
    이미지 3번에서 요구하신 목표 물성 기반 자동 성분/공정 도출 로직입니다.
    """
    target_ys = targets['ys']
    target_ts = targets['ts']
    target_cvn = targets['cvn']
    target_temp = targets['test_temp']
    section_thick = targets['thick']
    
    # 강도 타겟 기반 탄소(C) 함량 역산
    required_carbon = max(0.185, (target_ts - 395.0) / 1725.0)
    
    # 저온 인성 타겟 기반 니켈(Ni) 함량 역산
    if target_temp <= -101:
        required_ni = 4.38 + (target_cvn / 30.5)
    elif target_temp <= -46:
        required_ni = 2.58 + (target_cvn / 40.5)
    else:
        required_ni = 0.12
        
    # 망간(Mn) 및 기타 합금 설계
    required_mn = 1.68 if section_thick > 155 else 1.48
    
    # 20종 합금 설계 스펙 생성 (축약 없이 전개)
    alloy_design = {
        "C": round(required_carbon, 3), "Si": 0.485, "Mn": required_mn,
        "P": 0.008, "S": 0.002, "Cr": 0.688, "Mo": 0.388, "Ni": round(required_ni, 3),
        "Cu": 0.158, "V": 0.088, "Nb": 0.038, "Ti": 0.018, "Al": 0.052, "B": 0.0012,
        "N": 0.008, "As": 0.004, "Sn": 0.004, "Sb": 0.002, "Pb": 0.001, "Zr": 0.005
    }
    
    # 공정 시나리오 자동 생성
    p1_scenario = {
        "mode": "Quenching" if target_ys > 465 else "Normalizing",
        "temp": 935,
        "time": max(360, section_thick * 3.25),
        "cool": "수냉(WQ)" if target_ys > 475 else "공냉(AC)"
    }
    
    p2_scenario = {
        "mode": "Tempering",
        "temp": 650 if target_cvn > 85 else 620,
        "time": 240,
        "cool": "수냉(WQ)" if target_cvn > 65 else "공냉(AC)"
    }
    
    p3_scenario = {
        "mode": "S/R",
        "temp": 625,
        "time": 300,
        "cool": "공냉(AC)"
    }
    
    return {
        "alloy": alloy_design,
        "p1": p1_scenario,
        "p2": p2_scenario,
        "p3": p3_scenario
    }