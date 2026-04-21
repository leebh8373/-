def predict_properties(ceq, pcm, combined_hjp, thickness, p_type, t_cool, extra_list):
    # 공정별 기본 강도 계수
    factors = {
        'Annealing': 0.78, 'Normalizing': 1.0, 'Solution Annealing': 0.85,
        'Quenching (Oil)': 1.30, 'Quenching (Water)': 1.52
    }
    f_base = factors.get(p_type, 1.0)
    f_cool = 0.96 if "노냉" in t_cool else 1.0
    mass_effect = 1 - (thickness / 1500)
    
    # HJP에 따른 연화량 계산
    softening = max(0, combined_hjp - 14.2) * 60
    
    # 물성치 산출 수식 (Ceq 기반)
    ts = (ceq * 840 + pcm * 360 - softening + 185) * f_base * f_cool * mass_effect
    ys = ts * (0.85 if 'Quenching' in p_type else 0.73)
    el = 46 - (ts / 23) + (combined_hjp * 0.8)
    ra = el * 1.82
    hb = ts / 3.40
    
    # 충격치 및 취성 패널티
    cvn_penalty = 0.82 if "노냉" in t_cool else 1.0
    cvn = ((combined_hjp * 23) - (ceq * 92) + (125 / (thickness**0.5))) * cvn_penalty
    
    # 잔류 응력 예측
    base_rs = 380 if 'Quenching' in p_type else 160
    if 'S/R' in extra_list: base_rs *= 0.25
    if 'PWHT' in extra_list: base_rs *= 0.12
    if p_type == 'Solution Annealing': base_rs *= 0.18
    
    return {
        'TS': round(max(ts, 350), 1), 'YS': round(max(ys, 250), 1),
        'EL': round(max(el, 5), 1), 'RA': round(max(ra, 10), 1),
        'CVN': round(max(cvn, 2), 1), 'HB': round(max(hb, 110), 0),
        'RS': round(base_rs, 1)
    }

def suggest_heat_treatment(ceq, target_ts, target_cvn, thickness):
    # 역설계 간이 모델
    primary = "Quenching (Water)" if target_ts > 680 else "Normalizing"
    req_hjp = 14.8 + (ceq * 820 + 200 - target_ts) / 58
    temp = (max(14.0, min(19.5, req_hjp)) * 1000 / 20.6) - 273.15
    return {'primary': primary, 'temp': round(temp, 0), 'time': 4.0, 'cooling': '공냉 (Air)'}