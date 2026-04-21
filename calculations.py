import math

# =================================================================
# [SECTION 1] 1차 메인 열처리 물리 엔진 (Austenitizing & Quenching)
# =================================================================
def calculate_1st_stage_physics(group, comp, p1, thickness):
    """
    1차 열처리 종류(Quenching, Normalizing 등)와 20종 합금 원소의 
    물리적 기여도를 전수 나열하여 초기 강도를 산출합니다.
    """
    
    # 1. Base Matrix 기초 강도 (Pure Iron 및 기본 조직 강도)
    # 27년 현장 데이터를 기반으로 한 기초 강도 상수
    base_fe_strength = 370.5 

    # 2. 20종 합금 원소별 개별 고용/석출 강화 기여도 (물리적 전수 나열)
    # 팀장님 검증용: 각 원소의 기여 계수를 독립 변수로 분리하여 신뢰성 확보
    c_contrib  = comp.get('C', 0)  * 1510.0  # 탄소: 전위 이동 방해 및 마르텐사이트 경도 결정
    si_contrib = comp.get('Si', 0) * 115.0   # 규소: 페라이트 고용 강화 및 뜨임 저항성
    mn_contrib = comp.get('Mn', 0) * 195.0   # 망간: 경화능 향상 및 임계 냉각 속도 저하
    p_contrib  = comp.get('P', 0)  * 910.0   # 인: 입계 편석 및 고용 강화 (취성 유발 인자)
    s_contrib  = comp.get('S', 0)  * 180.0   # 황: 비금속 개재물(MnS) 형성 및 인성 저하
    cr_contrib = comp.get('Cr', 0) * 135.0   # 크롬: 경화능 및 내식성, 탄화물 형성 기여
    mo_contrib = comp.get('Mo', 0) * 315.0   # 몰리브덴: 뜨임 취성 방지 및 고온 강도
    ni_contrib = comp.get('Ni', 0) * 85.0    # 니켈: 저온 인성 비약적 향상 및 기질 강화
    cu_contrib = comp.get('Cu', 0) * 70.0    # 구리: 석출 강화 및 내식성 향상
    v_contrib  = comp.get('V', 0)  * 450.0   # 바나듐: 결정립 미세화 및 강력한 탄화물 형성
    nb_contrib = comp.get('Nb', 0) * 710.0   # 나이오븀: 고온 강도 및 결정립 성장 억제
    ti_contrib = comp.get('Ti', 0) * 590.0   # 티타늄: 질화물 형성 및 결정립 조대화 방지
    al_contrib = comp.get('Al', 0) * 55.0    # 알루미늄: 탈산 및 결정립 미세화 기여
    b_contrib  = comp.get('B', 0)  * 4200.0  # 붕소: 극미량으로 경화능 극대화
    n_contrib  = comp.get('N', 0)  * 550.0    # 질소: 침입형 고용 강화 및 질화물 형성
    as_contrib = comp.get('As', 0) * 42.0    # 비소: 미량 잔류 원소(Tramp Element)
    sn_contrib = comp.get('Sn', 0) * 35.0    # 주석: 입계 취성 영향 인자
    sb_contrib = comp.get('Sb', 0) * 45.0    # 안티모니: 저온 취성 가속화 원소
    pb_contrib = comp.get('Pb', 0) * 25.0    # 납: 가공성 영향 및 결함 유발 가능성
    zr_contrib = comp.get('Zr', 0) * 72.0    # 지르코늄: 조직 안정화 및 개재물 제어
    
    # 3. 화학적 잠재 강도(Total Chemical Potential) 합산
    # 모든 원소의 영향력을 합산하여 재료의 본질적 한계 강도 설정
    total_chemical_potential = (
        base_fe_strength + c_contrib + si_contrib + mn_contrib + p_contrib + 
        s_contrib + cr_contrib + mo_contrib + ni_contrib + cu_contrib + 
        v_contrib + nb_contrib + ti_contrib + al_contrib + b_contrib + 
        n_contrib + as_contrib + sn_contrib + sb_contrib + pb_contrib + zr_contrib
    )

    # 4. 1차 열처리 종류(Process Type)에 따른 조직 변태 계수
    # [중요] Quenching 시 조직 강도가 비약적으로 상승함을 수식화
    process_type = p1.get('type', 'Quenching')
    if process_type == "Quenching":
        process_modifier = 1.38   # 마르텐사이트 변태 가중치
    elif process_type == "Normalizing":
        process_modifier = 1.18   # 미세 펄라이트 가중치
    elif process_type == "Annealing":
        process_modifier = 0.95   # 조대 펄라이트 가중치
    elif process_type == "Solution Treatment":
        process_modifier = 1.22   # 고용체 강화 가중치
    else:
        process_modifier = 1.0

    # 5. 1차 가열 온도(Austenitizing Temp) 및 결정립 조대화 로직
    # 온도가 높을수록 결정립이 성장하여 Hall-Petch 효과에 의해 강도가 저하됨
    austenitizing_temp = p1.get('temp', 930)
    grain_size_factor = 1.0 - (max(0, austenitizing_temp - 910) * 0.00065)
    
    # 6. 유지 시간(Soaking Time)에 따른 물리적 영향
    # 확산 거리에 따른 조직 안정화 및 조대화 비례 관계
    soaking_time = p1.get('time', 360)
    time_impact_factor = 1.0 - (0.032 * math.log10(max(1, soaking_time)))
    
    # 7. 1차 냉각 방식(Cooling Method)의 냉각능(Severity of Quench)
    # 냉각 매체에 따른 마르텐사이트 분율 및 잔류 오스테나이트량 간접 반영
    cooling_mode = p1.get('cooling', '수냉(WQ)')
    cooling_severity_map = {
        "수냉(WQ)": 2.55, 
        "유냉(OQ)": 2.15, 
        "공냉(AC)": 1.75, 
        "노냉(FC)": 1.25
    }
    cooling_power = cooling_severity_map.get(cooling_mode, 1.0)
    
    # 8. 두께(Thickness)에 따른 질량 효과 (Mass Effect)
    # 단면이 두꺼울수록 중심부 냉각 속도가 저하되어 강도가 급감함
    mass_effect_loss = 1.0 - (thickness * 0.00085)
    
    # [최종 1차 계산치] 
    # 초기 주조 또는 열처리 직후의 예측 인장강도
    ts_initial = (total_chemical_potential * process_modifier * grain_size_factor * time_impact_factor * cooling_power * mass_effect_loss)
    
    return ts_initial


# =================================================================
# [SECTION 2] 후속 공정 (Tempering / SR) 및 최종 물성 전이
# =================================================================
def get_final_expert_simulation(group, ts_1st, p2, p3, test_temp, comp):
    """
    2차, 3차 후속 열처리와 각각의 냉각 방식이 최종 기계적 성질에 미치는 영향
    """
    
    # 1. Hollomon-Jaffe Parameter (HJP) 연화 로직
    # 뜨임 온도와 시간에 따른 전위 밀도 감소 및 탄화물 성장을 수식화
    def calculate_hjp_loss(temp, time, p_type):
        if p_type == "None" or time <= 0:
            return 0.0
        # Kelvin 온도 변환 및 hr 단위 변환
        k_temp = temp + 273.15
        log_time = math.log10(max(0.1, time / 60))
        hjp_value = k_temp * (20 + log_time)
        # 공정별 연화 상수 차별화 (Tempering vs Stress Relieving)
        divisor = 43500 if p_type == "Tempering" else 56500
        return hjp_value / divisor

    softening_loss_p2 = calculate_hjp_loss(p2['temp'], p2['time'], p2['type'])
    softening_loss_p3 = calculate_hjp_loss(p3['temp'], p3['time'], p3['type'])
    
    # 2. 후속 공정 냉각 방식에 따른 물성 보정
    # 뜨임 후 냉각 속도가 빠를수록 강도를 소폭 유리하게 가져감
    def get_cooling_correction(mode):
        if "수냉" in mode: return 1.09
        if "유냉" in mode: return 1.05
        if "노냉" in mode: return 0.92
        return 1.0

    c_mod_p2 = get_cooling_correction(p2.get('cooling', '공냉(AC)'))
    c_mod_p3 = get_cooling_correction(p3.get('cooling', '공냉(AC)'))
    
    # 3. 최종 인장강도(TS) 산출
    # 1차 강도에서 연화 손실과 냉각 보정을 순차 적용
    ts_final = ts_1st * (1.0 - softening_loss_p2) * (1.0 - softening_loss_p3) * c_mod_p2 * c_mod_p3
    
    # 4. 항복강도(YS) 및 항복비(Yield Ratio) 계산
    # 열처리 상태에 따른 항복비 결정 (Tempering 상태는 약 0.92 이상)
    base_yield_ratio = 0.95 if p2['type'] == "Tempering" else 0.84
    # 냉각 방식이 빠를수록 항복비 상승 가중치
    if "수냉" in p2['cooling']: base_yield_ratio += 0.02
    ys_final = ts_final * base_yield_ratio
    
    # 5. 연신율(EL) 및 단면수축률(RA) 계산
    # 강도와 연성은 반비례 관계 (Ductility Calculation)
    elongation = 30.5 * (630 / ts_final)**0.5 + (softening_loss_p2 + softening_loss_p3) * 62
    reduction_area = elongation * 2.22
    
    # 6. 브리넬 경도(HB) 환산
    hardness_hb = ts_final / 3.22
    
    # 7. 저온 충격치(CVN) 및 뜨임 취성(Temper Embrittlement) 시뮬레이션
    # [핵심] 냉각 방식이 '노냉(FC)'일 경우 취성 지수를 적용하여 충격치를 대폭 삭감
    embrittlement_penalty = 1.0
    if p2['cooling'] == "노냉(FC)" or p3['cooling'] == "노냉(FC)":
        embrittlement_penalty = 0.65  # 27년 현장 데이터 기반 취성 손실치
        
    ni_content = comp.get('Ni', 0)
    # 연성-취성 천이 온도(DBTT) 및 Upper Shelf Energy(USE) 계산
    # 니켈은 DBTT를 낮추고, 탄소와 인은 DBTT를 높임
    transition_temp = -52.0 - (ni_content * 42.0) + (comp.get('C', 0) * 95.0) + (comp.get('P', 0) * 1350)
    upper_shelf = 195.0 + (ni_content * 75.0) - (comp.get('P', 0) * 1300.0)
    
    # 시그모이드 함수를 이용한 온도별 충격 에너지 곡선 구현
    cvn_energy = (5.0 + (upper_shelf - 5.0) / (1 + math.exp(-0.1 * (test_temp - transition_temp)))) * embrittlement_penalty
    
    return {
        "ys": round(ys_final, 1),
        "ts": round(ts_final, 1),
        "el": round(elongation, 1),
        "ra": round(reduction_area, 1),
        "hb": round(hardness_hb, 1),
        "cvn": round(cvn_energy, 1),
        "org": "Fully Tempered Martensite" if softening_loss_p2 > 0.1 else "As-HT Structure",
        "lat": "BCC (Body-Centered Cubic)"
    }


# =================================================================
# [SECTION 3] 전문가용 역설계 엔진 (Inverse Engineering Engine)
# =================================================================
def run_expert_inverse_engine(targets):
    """
    이미지 3번의 비어 있던 탭을 채우는 핵심 로직.
    목표 물성을 입력받아 최적의 화학 성분(20종)과 1~3차 공정 조건을 역산합니다.
    """
    target_ys = targets['ys']
    target_ts = targets['ts']
    target_cvn = targets['cvn']
    test_temp = targets['test_temp']
    thickness = targets['thick']

    # 1. 인장강도 목표 기반 탄소(C)량 역설계
    # 강도 기여도를 역산하여 필요한 최소 탄소량 도출
    required_c = max(0.16, (target_ts - 375) / 1620.0)
    
    # 2. 저온 인성 목표 기반 니켈(Ni) 및 망간(Mn) 함량 설계
    # 특정 시험 온도에서 목표 충격치를 얻기 위한 합금 설계 가이드라인
    if test_temp <= -101:
        recommended_ni = 3.8 + (target_cvn / 40.0)
    elif test_temp <= -46:
        recommended_ni = 2.2 + (target_cvn / 50.0)
    else:
        recommended_ni = 0.0 # 일반 저합금강 수준
        
    recommended_mn = 1.55 if thickness > 120 else 1.35
    
    # 3. 1차 공정 파라미터 역설계 (Main HT)
    # 두께가 80mm를 넘거나 YS가 고강도인 경우 Quenching 필수 제안
    if target_ys > 420 or thickness > 80:
        p1_mode = "Quenching"
        p1_cool = "수냉(WQ)"
    else:
        p1_mode = "Normalizing"
        p1_cool = "공냉(AC)"
        
    p1_temp = 920 if required_c > 0.22 else 940
    p1_time = max(300, thickness * 2.5) # 두께당 유지시간 가중치 적용
    
    # 4. 2차/3차 후속 공정 설계 (취성 회피 전략)
    # 충격치 목표가 높으면 Tempering 후 반드시 수냉을 하도록 설계안 도출
    p2_cool = "수냉(WQ)" if target_cvn > 70 else "공냉(AC)"
    p2_temp = 630 if target_cvn > 80 else 595
    
    # 5. 최종 20종 성분 추천 리스트 생성
    # 현장에서 가장 안정적인 밸런스를 갖는 합금 조합 제안
    alloy_design = {
        "C": round(required_c, 3), "Si": 0.38, "Mn": recommended_mn, "P": 0.010, "S": 0.002,
        "Cr": 0.55, "Mo": 0.25, "Ni": round(recommended_ni, 3), "Cu": 0.15, "V": 0.05,
        "Nb": 0.03, "Ti": 0.015, "Al": 0.035, "B": 0.0012, "N": 0.008,
        "As": 0.004, "Sn": 0.004, "Sb": 0.002, "Pb": 0.001, "Zr": 0.005
    }
    
    return {
        "alloy": alloy_design,
        "p1": {"mode": p1_mode, "temp": p1_temp, "time": p1_time, "cool": p1_cool},
        "p2": {"mode": "Tempering", "temp": p2_temp, "time": 240, "cool": p2_cool},
        "p3": {"mode": "S/R", "temp": 620, "time": 300, "cool": "공냉(AC)"}
    }