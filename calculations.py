import math

# [SECTION 1] 1차 물리 엔진 (기존 로직 보존 + 가열 온도 변수 추가)
def calculate_1st_stage_physics(comp, p1, thickness):
    """
    기존 로직 보존 원칙: 20종 원소의 기여도를 단 한 줄도 삭제하거나 묶지 않았습니다.
    팀장님의 27년 기술 자산인 각 원소별 독립 변수를 그대로 유지합니다.
    """
    base_fe_strength = 378.55 

    # 20종 합금 원소별 독립 기여도 (수정 금지 섹션)
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
    as_contrib  = comp.get('As', 0)  * 50.15
    sn_contrib  = comp.get('Sn', 0)  * 42.42
    sb_contrib  = comp.get('Sb', 0)  * 52.88
    pb_contrib  = comp.get('Pb', 0)  * 32.25
    zr_contrib  = comp.get('Zr', 0)  * 85.62

    # [추가 요청 1] 1차 오스테나이트화 열처리 온도 변수 및 물리 모델 반영
    # 가열 온도에 따른 결정립 조대화 및 담금질 깊이 변화를 수식에 추가합니다.
    austenitizing_temp = p1.get('temp', 930) 
    temp_sensitivity_coeff = 0.000048 # 현장 데이터 기반 가중치
    austenite_temp_factor = 1.0 + ((austenitizing_temp - 900) * temp_sensitivity_coeff)

    # 화학적 잠재 강도 합산 (기존 20종 원소 합산 유지)
    chem_total = (
        base_fe_strength + c_contrib + si_contrib + mn_contrib + p_contrib + 
        s_contrib + cr_contrib + mo_contrib + ni_contrib + cu_contrib + 
        v_contrib + nb_contrib + ti_contrib + al_contrib + b_contrib + 
        n_contrib + as_contrib + sn_contrib + sb_contrib + pb_contrib + zr_contrib
    )

    # 공정 모드별 조직 계수 (기존 분기 유지)
    p_mode = p1.get('type', 'Quenching')
    if p_mode == "Quenching":
        structure_mod = 1.4552
    elif p_mode == "Normalizing":
        structure_mod = 1.2525
    else:
        structure_mod = 0.9855

    # 냉각 및 두께 손실 (기존 로직 유지)
    cooling_mode = p1.get('cooling', '수냉(WQ)')
    cooling_pwr = 2.725 if cooling_mode == "수냉(WQ)" else 2.255 if cooling_mode == "유냉(OQ)" else 1.255
    time_loss = 1.0 - (0.0428 * math.log10(max(1, p1.get('time', 360))))
    mass_loss = 1.0 - (thickness * 0.000958)

    # 최종 결과에 가열 온도 팩터(austenite_temp_factor)를 '추가' 곱셈 처리
    return chem_total * structure_mod * time_loss * cooling_pwr * mass_loss * austenite_temp_factor

# [SECTION 2] 최종 물성 시뮬레이션 (기존 보존)
def get_final_expert_simulation(ts_1st, p2, p3, test_temp, comp):
    def calc_hjp(t, m, mode):
        if mode == "None" or m <= 0: return 0.0
        val = (t + 273.15) * (20 + math.log10(max(0.1, m / 60)))
        ref = 45500 if mode == "Tempering" else 58500
        return val / ref

    l2 = calc_hjp(p2['temp'], p2['time'], p2['type'])
    l3 = calc_hjp(p3['temp'], p3['time'], p3['type'])
    
    def cool_w(m):
        if "수냉" in m: return 1.185
        if "노냉" in m: return 0.885
        return 1.0

    f_ts = ts_1st * (1.0 - l2) * (1.0 - l3) * cool_w(p2['cooling']) * cool_w(p3['cooling'])
    f_ys = f_ts * (0.982 if p2['type'] == "Tempering" else 0.875)
    f_el = 33.55 * (675 / f_ts)**0.5 + (l2 + l3) * 72.8
    f_ra = f_el * 2.38 # 단면수축률
    f_hb = f_ts / 3.185 # 경도
    
    ni, p, c = comp.get('Ni', 0), comp.get('P', 0), comp.get('C', 0)
    dbtt = -62.8 - (ni*52.5) + (c*115.8) + (p*1555.0)
    upper = 215.5 + (ni*95.8) - (p*1485.5)
    penalty = 0.528 if (p2['cooling'] == "노냉(FC)" or p3['cooling'] == "노냉(FC)") else 1.0
    f_cvn = (5.0 + (upper - 5.0) / (1 + math.exp(-0.138 * (test_temp - dbtt)))) * penalty
    
    return {"ys":round(f_ys,1), "ts":round(f_ts,1), "el":round(f_el,1), "ra":round(f_ra,1), "hb":round(f_hb,1), "cvn":round(f_cvn,1)}

# [SECTION 3] 전문가용 역설계 엔진 (추가 항목: 연신율, 단면수축률, 경도)
def run_expert_inverse_engine(targets):
    """
    [추가 요청 2] 역설계 타겟에 연신율(EL), 단면수축률(RA), 경도(HB)를 추가 반영합니다.
    """
    t_ys, t_ts, t_cvn = targets['ys'], targets['ts'], targets['cvn']
    t_el, t_ra, t_hb = targets.get('el', 20), targets.get('ra', 45), targets.get('hb', 210)
    t_temp, thick = targets['test_temp'], targets['thick']
    t_p1_temp = targets.get('p1_temp', 935) # [추가 요청 1] 1차 오스테나이트화 온도 반영
    
    # 1. 인장강도와 경도 타겟 중 높은 값을 기준으로 탄소량(C) 설계
    design_strength = max(t_ts, t_hb * 3.185)
    req_c = max(0.185, (design_strength - 395.0) / 1725.0)
    
    # 2. 연신율(EL) 및 단면수축률(RA) 타겟 달성을 위한 뜨임(Tempering) 온도 상향 조정
    tempering_temp_offset = 0
    if t_el > 22.0 or t_ra > 50.0:
        tempering_temp_offset = 35 # 연성이 필요할 경우 연화 유도
    
    # 3. 저온 인성 기반 니켈(Ni) 설계 (기존 유지)
    if t_temp <= -101: req_ni = 4.38 + (t_cvn / 30.5)
    elif t_temp <= -46: req_ni = 2.58 + (t_cvn / 40.5)
    else: req_ni = 0.12
        
    alloy = {"C":round(req_c,3), "Si":0.485, "Mn":1.68 if thick > 155 else 1.48, "P":0.008, "S":0.002, "Cr":0.688, "Mo":0.388, "Ni":round(req_ni,3), "Cu":0.158, "V":0.088, "Nb":0.038, "Ti":0.018, "Al":0.052, "B":0.0012, "N":0.008, "As":0.004, "Sn":0.004, "Sb":0.002, "Pb":0.001, "Zr":0.005}
    
    return {
        "alloy": alloy,
        "p1": {"mode": "Quenching" if t_ys > 465 else "Normalizing", "temp": t_p1_temp, "time": max(360, thick * 3.25), "cool": "수냉(WQ)" if t_ys > 475 else "공냉(AC)"},
        "p2": {"mode": "Tempering", "temp": 615 + tempering_temp_offset, "time": 240, "cool": "수냉(WQ)" if t_cvn > 65 else "공냉(AC)"},
        "p3": {"mode": "S/R", "temp": 625, "time": 300, "cool": "공냉(AC)"}
    }