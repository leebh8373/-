import math

def calculate_ceq(c, mn, cr, mo, v, ni, cu):
    return c + mn/6 + (cr + mo + v)/5 + (ni + cu)/15

def calculate_holding_time(thickness, k=2.4):
    """두께(mm)에 따른 유지시간(min) 계산 (심부 균일화 반영)"""
    return thickness * k

def predict_structure_and_lattice(treatment, cooling):
    """냉각 방식 및 열처리에 따른 조직과 격자구조 판정"""
    if cooling == "수냉(WQ)":
        return "Martensite", "BCT (Body-Centered Tetragonal)"
    elif cooling == "유냉(OQ)":
        return "Tempered Martensite / Bainite", "BCC (Body-Centered Cubic)"
    elif treatment == "Normalizing":
        return "Fine Pearlite + Ferrite", "BCC (Body-Centered Cubic)"
    elif treatment == "Annealing":
        return "Coarse Pearlite + Ferrite", "BCC (Body-Centered Cubic)"
    else:
        return "Pearlite + Ferrite", "BCC"

def calculate_properties(comp, treatment, thickness, cooling):
    """냉각 속도와 항복비를 반영한 물성 예측"""
    # 1. 베이스 인장강도 계산
    base_ts = 400 + (comp['C']*1000) + (comp['Mn']*100) + (comp['Cr']*70) + (comp['Mo']*150)
    
    # 2. 냉각 속도 가중치
    cooling_map = {"수냉(WQ)": 1.55, "유냉(OQ)": 1.35, "공냉(AC)": 1.0, "노냉(FC)": 0.85}
    cf = cooling_map.get(cooling, 1.0)
    
    # 3. 두께에 따른 강도 저하 (질량 효과)
    mass_effect = 1.0 - (thickness * 0.0008)
    
    ts = base_ts * cf * mass_effect
    
    # 4. 항복비(Yield Ratio) 적용 (YS와 TS 차이 발생)
    yr_map = {"Annealing": 0.58, "Normalizing": 0.68, "Q&T": 0.86}
    yr = yr_map.get(treatment, 0.75)
    ys = ts * yr
    
    # 5. 연신율 및 단면수축률
    el = 45 - (ts / 35)
    ra = el * 1.6
    
    return round(ys, 1), round(ts, 1), round(el, 1), round(ra, 1)

def predict_cvn(base_cvn, test_temp):
    """시험 온도에 따른 충격치 천이 곡선 적용"""
    # 20도 대비 온도 하락에 따른 취성 전이 시뮬레이션
    factor = math.exp(0.025 * (test_temp - 20))
    return round(base_cvn * factor, 1)

def reverse_design_logic(target_ts, thickness, treatment):
    """요구 물성에 따른 성분 및 공정 역설계"""
    # 목표 TS를 달성하기 위한 필요 Ceq 추정
    req_ceq = (target_ts / 1.3) / 550
    
    # 두께별 유지시간
    h_time = calculate_holding_time(thickness)
    
    # 조직 판정
    org, lattice = predict_structure_and_lattice(treatment, "공냉(AC)" if treatment != "Q&T" else "유냉(OQ)")
    
    return {
        "C": "0.18 ~ 0.23", "Mn": "1.30 ~ 1.60", "Cr": "0.20 ~ 0.50",
        "Ceq": round(req_ceq, 3), "Time": h_time, "Org": org, "Lattice": lattice
    }