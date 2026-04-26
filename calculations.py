import math

__version__ = "6.3.0" # Temp Prediction & Thickness Target Upgrade

# [SECTION 1] 전문가용 1차 물리 엔진
def calculate_1st_stage_physics(comp, p1, thickness, **kwargs):
    base_fe_strength = 378.55 
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

    austenitizing_temp = p1.get('temp', 930) 
    austenite_temp_factor = 1.0 + ((austenitizing_temp - 900) * 0.000048)

    chem_total = (
        base_fe_strength + c_contrib + si_contrib + mn_contrib + p_contrib + 
        s_contrib + cr_contrib + mo_contrib + ni_contrib + cu_contrib + 
        v_contrib + nb_contrib + ti_contrib + al_contrib + b_contrib + n_contrib
    )

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

    hardenability_index = (comp.get('Mn', 0)*0.5 + comp.get('Cr', 0)*0.8 + comp.get('Mo', 0)*1.2 + 0.1)
    mass_effect = 1.0 / (1.0 + (thickness / (250 * cooling_pwr * (1 + hardenability_index)))**1.8)
    time_loss = 1.0 - (0.0428 * math.log10(max(1, p1.get('time', 360))))

    return chem_total * structure_mod * time_loss * cooling_pwr * mass_effect * austenite_temp_factor

def calculate_ceq_by_standard(comp, standard, **kwargs):
    c, si, mn = comp.get('C', 0), comp.get('Si', 0), comp.get('Mn', 0)
    cr, mo, v = comp.get('Cr', 0), comp.get('Mo', 0), comp.get('V', 0)
    ni, cu, b = comp.get('Ni', 0), comp.get('Cu', 0), comp.get('B', 0)
    
    if standard == "IIW (ASTM/ASME/EN)":
        val = c + mn/6 + (cr+mo+v)/5 + (ni+cu)/15
        name = "Ceq (IIW)"
    elif standard == "JIS":
        val = c + mn/6 + si/24 + ni/40 + cr/5 + mo/4 + v/14
        name = "Ceq (JIS)"
    elif standard == "Pcm (API/NORSOK)":
        val = c + si/30 + (mn+cu+cr)/20 + ni/60 + mo/15 + v/10 + 5*b
        name = "Pcm (Ito-Bessyo)"
    elif standard == "CET (European)":
        val = c + (mn+mo)/10 + (cr+cu)/20 + ni/40
        name = "CET"
    else:
        val = c + mn/6 
        name = "Ceq"
    return name, round(val, 3)

def predict_microstructure(comp, p1, thickness, **kwargs):
    cooling = p1.get('cooling', '수냉(WQ)')
    p_type = p1.get('type', 'Quenching')
    hardenability = (comp.get('C', 0)*0.5 + comp.get('Mn', 0)*0.7 + comp.get('Cr', 0)*0.5 + comp.get('Mo', 0)*1.0)
    thickness_factor = thickness / 100
    
    if p_type == "Quenching":
        if "수냉" in cooling:
            if hardenability > 0.4 and thickness_factor < 1.5:
                return "Martensite (M)", "침상 구조의 높은 경도를 가진 마르텐사이트 조직이 지배적입니다."
            else:
                return "Martensite + Bainite (M+B)", "냉각 속도 저하로 마르텐사이트와 베이나이트가 혼합된 조직입니다."
        elif "유냉" in cooling:
            return "Bainite + Martensite (B+M)", "변태 속도가 느려 베이나이트가 주를 이루며 일부 마르텐사이트가 존재합니다."
        else:
            return "Bainite (B)", "완만한 냉각으로 인해 베이나이트 조직이 형성되었습니다."
    elif p_type == "Normalizing":
        if hardenability > 0.5:
            return "Bainite + Pearlite (B+P)", "합금 원소 영향으로 미세한 펄라이트와 베이나이트가 혼합되었습니다."
        else:
            return "Ferrite + Pearlite (F+P)", "표준적인 정규화 조직으로 페라이트와 펄라이트가 균일하게 분포합니다."
    else:
        return "Ferrite + Coarse Pearlite (F+P)", "매우 완만한 냉각으로 인해 조대한 펄라이트와 페라이트가 형성되었습니다."

# [SECTION 2] 최종 물성 시뮬레이션
def run_simulation_v6(ts_1st, p2, p3, test_temp, comp, p1, thickness, ceq_standard, **kwargs):
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
    if p2['type'] == "Tempering": yr = 0.865 + (l2 * 0.05)
    else: yr = 0.725
    f_ys = f_ts * yr

    f_el = 33.55 * (675 / max(400, f_ts))**0.65 + (l2 + l3) * 65.2
    ra_factor = 2.45 - (f_ts / 2500)
    f_ra = f_el * ra_factor 
    f_hb = f_ts / 3.25 
    
    ni, p, c = comp.get('Ni', 0), comp.get('P', 0), comp.get('C', 0)
    dbtt = -65.0 - (ni*55.5) + (c*120.0) + (p*1850.0) + (comp.get('S', 0)*2500.0)
    upper = 220.0 + (ni*98.5) - (p*1600.0) - (comp.get('S', 0)*3000.0)
    penalty = 0.55 if (p2['cooling'] == "노냉(FC)" or p3['cooling'] == "노냉(FC)") else 1.0
    f_cvn = (5.0 + (upper - 5.0) / (1 + math.exp(-0.135 * (test_temp - dbtt)))) * penalty
    
    ceq_label, ceq_val = calculate_ceq_by_standard(comp, ceq_standard)
    micro_name, micro_desc = predict_microstructure(comp, p1, thickness)
    
    return {
        "ys":round(f_ys,1), "ts":round(f_ts,1), "el":round(f_el,1), 
        "ra":round(f_ra,1), "hb":round(f_hb,1), "cvn":round(f_cvn,1),
        "ceq_val": ceq_val, "ceq_label": ceq_label, "micro_name": micro_name, "micro_desc": micro_desc
    }

# [SECTION 3] 전문가용 역설계 엔진 (v6.3 - 온도 자동 예측 및 두께 포함)
def run_inverse_v6(targets, **kwargs):
    t_ys, t_ts, t_cvn = targets['ys'], targets['ts'], targets['cvn']
    t_el, t_ra, t_hb = targets.get('el', 20), targets.get('ra', 45), targets.get('hb', 210)
    t_temp, thick = targets['test_temp'], targets['thick']
    t_ceq_standard = targets.get('ceq_standard', 'IIW (ASTM/ASME/EN)')
    
    comments = []
    design_strength = max(t_ts, t_hb * 3.25)
    
    req_mo, req_cr, req_mn = 0.05, 0.15, 1.45
    if thick > 150:
        req_mo = 0.25 + (thick - 150) * 0.001
        req_cr = 0.55 + (thick - 150) * 0.002
        req_mn = 1.65
        comments.append(f"두께({thick}mm) 질량 효과 극복을 위해 Mo, Cr 경화능 원소를 증량 설계하였습니다.")
    
    strength_from_alloys = (req_mo * 330) + (req_cr * 142) + (req_mn * 205)
    req_c = max(0.18, (design_strength / (1.2 * 0.9) - 380 - strength_from_alloys) / 1545)
    
    tempering_temp_offset = 0
    if t_el > 23.0 or t_ra > 52.0:
        tempering_temp_offset = 40
        comments.append("목표 연성(EL/RA) 달성을 위해 뜨임 온도를 상향 조정하였습니다.")
    
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

    # 1차 오스테나이트화 온도 자동 예측
    predicted_p1_temp = 905 + (req_cr * 12) + (req_mo * 15) + (thick / 15)
    predicted_p1_temp = min(1100, max(880, round(predicted_p1_temp / 5) * 5))
    comments.append(f"추천 1차 오스테나이트화 온도: {predicted_p1_temp}℃ (합금 성분 및 두께 영향 반영)")

    ceq_label, ceq_val = calculate_ceq_by_standard(alloy, t_ceq_standard)
    if ceq_val > 0.48:
        comments.append(f"주의: 제안된 성분의 {ceq_label} 값({ceq_val})이 높아 예열 및 후열처리가 필수적입니다.")

    return {
        "alloy": alloy,
        "p1": {"mode": "Quenching" if t_ys > 450 else "Normalizing", "temp": predicted_p1_temp, "time": max(360, thick * 3.5), "cool": "수냉(WQ)" if t_ys > 460 else "공냉(AC)"},
        "p2": {"mode": "Tempering", "temp": 600 + tempering_temp_offset, "time": max(240, thick * 1.5), "cool": "수냉(WQ)" if t_cvn > 60 else "공냉(AC)"},
        "p3": {"mode": "S/R", "temp": 620, "time": 300, "cool": "공냉(AC)"},
        "comments": comments,
        "ceq_val": ceq_val, "ceq_label": ceq_label
    }