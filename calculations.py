import math

# [SECTION 1] 전문가용 1차 물리 엔진 (경화능 및 질량효과 정밀 반영)
def calculate_1st_stage_physics(comp, p1, thickness):
    """
    주강품의 합금 원소별 기여도와 두께에 따른 질량 효과(Mass Effect)를 정밀하게 계산합니다.
    """
    base_fe_strength = 378.55 

    # 20종 합금 원소별 독립 기여도 (연구 데이터 기반 고정값)
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

    # 1차 오스테나이트화 온도 팩터
    austenitizing_temp = p1.get('temp', 930) 
    temp_sensitivity_coeff = 0.000048 
    austenite_temp_factor = 1.0 + ((austenitizing_temp - 900) * temp_sensitivity_coeff)

    # 화학적 잠재 강도 합산
    chem_total = (
        base_fe_strength + c_contrib + si_contrib + mn_contrib + p_contrib + 
        s_contrib + cr_contrib + mo_contrib + ni_contrib + cu_contrib + 
        v_contrib + nb_contrib + ti_contrib + al_contrib + b_contrib + 
        n_contrib + as_contrib + sn_contrib + sb_contrib + pb_contrib + zr_contrib
    )

    # 냉각 방식 및 조직 계수
    p_mode = p1.get('type', 'Quenching')
    cooling_mode = p1.get('cooling', '수냉(WQ)')
    
    if p_mode == "Quenching":
        structure_mod = 1.4552 if "수냉" in cooling_mode else 1.3255
        cooling_pwr = 2.725 if "수냉" in cooling_mode else 2.255
    elif p_mode == "Normalizing":
        structure_mod = 1.2525
        cooling_pwr = 1.255
    else:
        structure_mod = 0.9855
        cooling_pwr = 0.855

    # [고도화] 질량 효과(Mass Effect) 정밀 모델링
    # 두께가 두꺼울수록, 냉각 속도가 느릴수록 강도가 지수함수적으로 감소하는 현상 반영
    # 합금 원소(Mn, Cr, Mo)가 많을수록 질량 효과에 의한 감소폭이 줄어듦(경화능 확보)
    hardenability_index = (comp.get('Mn', 0)*0.5 + comp.get('Cr', 0)*0.8 + comp.get('Mo', 0)*1.2 + 0.1)
    mass_effect = 1.0 / (1.0 + (thickness / (250 * cooling_pwr * (1 + hardenability_index)))**1.8)
    
    time_loss = 1.0 - (0.0428 * math.log10(max(1, p1.get('time', 360))))

    return chem_total * structure_mod * time_loss * cooling_pwr * mass_effect * austenite_temp_factor

# [SECTION 2] 최종 물성 시뮬레이션 (물성 상관관계 정밀화)
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

    # 최종 인장강도(TS) 계산
    f_ts = ts_1st * (1.0 - l2) * (1.0 - l3) * cool_w(p2['cooling']) * cool_w(p3['cooling'])
    
    # [고도화] 항복비(Yield Ratio)의 동적 적용
    # 조질(Q&T) 처리된 강재는 항복비가 높고(0.85~0.9), 소둔/정규화(A/N)는 낮음(0.65~0.75)
    if p2['type'] == "Tempering":
        yr = 0.865 + (l2 * 0.05) # 뜨임 온도가 높을수록 조직 안정화로 항복비 소폭 상승
    else:
        yr = 0.725
    f_ys = f_ts * yr

    # [고도화] 연신율 및 단면수축률 상관관계 (강도-연성 상충 관계 반영)
    f_el = 33.55 * (675 / max(400, f_ts))**0.65 + (l2 + l3) * 65.2
    # 단면수축률은 연신율의 함수이나 강도가 높을수록 그 비중이 줄어듬
    ra_factor = 2.45 - (f_ts / 2500)
    f_ra = f_el * ra_factor 
    
    # 브리넬 경도(HB)와 인장강도의 표준 상관관계
    f_hb = f_ts / 3.25 
    
    # [고도화] 충격치(CVN) 시그모이드 모델 (불순물 패널티 강화)
    ni, p, c = comp.get('Ni', 0), comp.get('P', 0), comp.get('C', 0)
    # 인(P)과 황(S)은 충격 인성을 급격히 저하시킴
    dbtt = -65.0 - (ni*55.5) + (c*120.0) + (p*1850.0) + (comp.get('S', 0)*2500.0)
    upper = 220.0 + (ni*98.5) - (p*1600.0) - (comp.get('S', 0)*3000.0)
    
    # 냉각 속도에 따른 템퍼 취성 패널티
    penalty = 0.55 if (p2['cooling'] == "노냉(FC)" or p3['cooling'] == "노냉(FC)") else 1.0
    f_cvn = (5.0 + (upper - 5.0) / (1 + math.exp(-0.145 * (test_temp - dbtt)))) * penalty
    
    return {
        "ys":round(f_ys,1), "ts":round(f_ts,1), "el":round(f_el,1), 
        "ra":round(f_ra,1), "hb":round(f_hb,1), "cvn":round(f_cvn,1)
    }

# [SECTION 3] 전문가용 역설계 엔진 (두께별 전략 합금 설계)
def run_expert_inverse_engine(targets):
    """
    목표 물성을 달성하기 위한 최적의 화학 성분과 열처리 조건을 제안합니다.
    제품 두께(Thickness)에 따른 경화능 확보 전략이 포함됩니다.
    """
    t_ys, t_ts, t_cvn = targets['ys'], targets['ts'], targets['cvn']
    t_el, t_ra, t_hb = targets.get('el', 20), targets.get('ra', 45), targets.get('hb', 210)
    t_temp, thick = targets['test_temp'], targets['thick']
    t_p1_temp = targets.get('p1_temp', 935) 
    
    comments = []
    
    # 1. 인장강도와 경도 타겟 중 높은 값을 기준으로 설계 강도 설정
    design_strength = max(t_ts, t_hb * 3.25)
    
    # 2. 질량 효과 극복을 위한 경화능 원소(Mo, Cr, Mn) 설계 전략
    req_mo = 0.05
    req_cr = 0.15
    req_mn = 1.45
    
    if thick > 150:
        req_mo = 0.25 + (thick - 150) * 0.001
        req_cr = 0.55 + (thick - 150) * 0.002
        req_mn = 1.65
        comments.append(f"두께({thick}mm) 질량 효과 극복을 위해 Mo, Cr 경화능 원소를 증량 설계하였습니다.")
    
    # 3. 강도 달성을 위한 탄소량(C) 역산
    # 두께와 합금 원소에 따른 보정치를 고려하여 탄소량 결정
    strength_from_alloys = (req_mo * 330) + (req_cr * 142) + (req_mn * 205)
    req_c = max(0.18, (design_strength / (1.2 * 0.9) - 380 - strength_from_alloys) / 1545)
    
    # 4. 연성(EL, RA) 확보를 위한 뜨임 온도 오프셋
    tempering_temp_offset = 0
    if t_el > 23.0 or t_ra > 52.0:
        tempering_temp_offset = 40
        comments.append("목표 연성(EL/RA) 달성을 위해 뜨임 온도를 상향 조정하였습니다.")
    
    # 5. 저온 인성 확보를 위한 니켈(Ni) 설계
    if t_temp <= -101: req_ni = 4.5 + (t_cvn / 28.0)
    elif t_temp <= -46: req_ni = 2.8 + (t_cvn / 35.0)
    else: req_ni = 0.15
    if req_ni > 1.0: comments.append(f"저온 충격치({t_cvn}J) 확보를 위해 Ni 함량을 {round(req_ni,2)}%로 제안합니다.")
        
    alloy = {
        "C":round(req_c,3), "Si":0.45, "Mn":round(req_mn,2), "P":0.008, "S":0.002, 
        "Cr":round(req_cr,2), "Mo":round(req_mo,2), "Ni":round(req_ni,2), "Cu":0.15, 
        "V":0.05 if design_strength > 750 else 0.01, "Nb":0.03, "Ti":0.015, "Al":0.04, 
        "B":0.001, "N":0.008, "As":0.004, "Sn":0.004, "Sb":0.002, "Pb":0.001, "Zr":0.005
    }
    
    # 용접성(Ceq) 체크
    ceq = alloy['C'] + alloy['Mn']/6 + (alloy['Cr']+alloy['Mo']+alloy['V'])/5 + (alloy['Ni']+alloy['Cu'])/15
    if ceq > 0.48:
        comments.append(f"주의: 제안된 성분의 탄소당량(Ceq={round(ceq,2)})이 높아 예열 및 후열처리가 필수적입니다.")

    return {
        "alloy": alloy,
        "p1": {"mode": "Quenching" if t_ys > 450 else "Normalizing", "temp": t_p1_temp, "time": max(360, thick * 3.5), "cool": "수냉(WQ)" if t_ys > 460 else "공냉(AC)"},
        "p2": {"mode": "Tempering", "temp": 600 + tempering_temp_offset, "time": max(240, thick * 1.5), "cool": "수냉(WQ)" if t_cvn > 60 else "공냉(AC)"},
        "p3": {"mode": "S/R", "temp": 620, "time": 300, "cool": "공냉(AC)"},
        "comments": comments,
        "ceq": round(ceq, 3)
    }