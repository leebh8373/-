import math

def calculate_ceq_pcm_ultimate(comp):
    """국제 표준 및 해양/원자력 규격 기반 탄소당량 및 용접지수 계산"""
    c = comp.get('C', 0); mn = comp.get('Mn', 0); cr = comp.get('Cr', 0)
    mo = comp.get('Mo', 0); v = comp.get('V', 0); ni = comp.get('Ni', 0)
    cu = comp.get('Cu', 0); si = comp.get('Si', 0); b = comp.get('B', 0)
    
    # IIW (International Institute of Welding) CE
    ceq = c + (mn / 6) + ((cr + mo + v) / 5) + ((ni + cu) / 15)
    # Ito & Bessyo (Welding Crack Susceptibility) Pcm
    pcm = c + (si / 30) + ((mn + cu + cr) / 20) + (ni / 60) + (mo / 15) + (v / 10) + (5 * b)
    
    return round(ceq, 4), round(pcm, 4)

def get_base_tensile_strength(group, comp):
    """20종 원소 각각의 기여도를 상세히 계산 (MPa/wt%)"""
    # 기본 철(Fe) 조직의 기재 강도
    ts_base = 355.0
    
    if "Stainless" in group:
        # 스테인리스강 특화 수식
        alloy_eff = (comp.get('Cr', 0) * 15.5) + (comp.get('Ni', 0) * 18.2) + (comp.get('N', 0) * 350.0)
    else:
        # 탄소강 및 저합금강 수식
        alloy_eff = (comp.get('C', 0) * 1320.0) + (comp.get('Mn', 0) * 155.0) + \
                    (comp.get('Si', 0) * 85.0) + (comp.get('Mo', 0) * 245.0) + \
                    (comp.get('Cr', 0) * 92.0) + (comp.get('V', 0) * 340.0) + \
                    (comp.get('Ni', 0) * 52.0) + (comp.get('Cu', 0) * 45.0) + \
                    (comp.get('Nb', 0) * 520.0) + (comp.get('Ti', 0) * 420.0) + \
                    (comp.get('B', 0) * 3200.0)
    
    # 유해 잔류 원소(Tramp Elements)에 의한 강도 미세 변화
    tramp_eff = (comp.get('As', 0) + comp.get('Sn', 0) + comp.get('Sb', 0)) * 12.0
    
    return ts_base + alloy_eff + tramp_eff

def apply_complex_ht_logic(group, base_ts, p1, p2, thickness, test_temp):
    """1차+2차+3차(SR) 및 충격/연신율 통합 계산"""
    # 1. 냉각 속도 및 질량 효과(Mass Effect)
    cooling_factors = {"수냉(WQ)": 1.9, "유냉(OQ)": 1.6, "공냉(AC)": 1.25, "노냉(FC)": 0.9}
    cf = cooling_factors.get(p1['cooling'], 1.0)
    # 대형 주물 단면 두께에 따른 강도 감쇄
    mass_effect = 1.0 - (thickness * 0.00055)
    
    ts_initial = base_ts * cf * mass_effect
    
    # 2. 2차 공정(Tempering / S/R / PWHT) 영향
    final_ts = ts_initial
    yr_ratio = 0.65
    el_base = 24.0 # 기본 연신율 시작점
    
    if p2['type'] != "None":
        # Hollomon-Jaffe Parameter (HJP) 계산
        temp_k = p2['temp'] + 273.15
        time_h = p2['time'] / 60.0
        hjp = temp_k * (20 + math.log10(time_h if time_h > 0 else 1))
        
        # 공정별 연화 계수 차별화
        div = 42000 if p2['type'] == "Tempering" else (50000 if p2['type'] == "S/R" else 45000)
        soft_ratio = hjp / div
        final_ts = ts_initial * (1.0 - soft_ratio)
        
        # 연신율 보정: 강도 하락분만큼 연성 상승
        el_base += (soft_ratio * 48)
        
        # 항복비(YR) 설정
        if "Stainless" in group: yr_ratio = 0.50
        elif p2['type'] == "Tempering": yr_ratio = 0.86
        elif p2['type'] == "S/R": yr_ratio = 0.76
        else: yr_ratio = 0.79

    final_ys = final_ts * yr_ratio
    final_el = el_base * (560 / final_ts) ** 0.5
    final_ra = final_el * 1.85 # 단면수축률 경험식
    
    # 3. 충격 에너지(CVN) 천이 곡선 계산
    # Ni 함량에 따른 DBTT(천이온도) 하락 반영
    dbtt = -30.0 - (comp.get('Ni', 0) * 20) + (comp.get('C', 0) * 55)
    upper_shelf = 160.0 + (comp.get('Ni', 0) * 40) - (comp.get('P', 0) * 800) - (comp.get('S', 0) * 2500)
    cvn = 5.0 + (upper_shelf - 5.0) / (1 + math.exp(-0.065 * (test_temp - dbtt)))
    
    return round(final_ys, 1), round(final_ts, 1), round(final_el, 1), round(ra, 1), round(cvn, 1)