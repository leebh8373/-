"""
Sentinel-Alpha casting steel property engine (upgraded)
Empirical engineering model for screening only. Not a substitute for qualified test data.
"""
import math

__version__ = "6.4.0"

ELEMENTS = ['C','Si','Mn','P','S','Cr','Mo','Ni','Cu','V','Nb','Ti','Al','B','N','As','Sn','Sb','Pb','Zr']


def _num(x, default=0.0):
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def normalize_comp(comp):
    return {e: max(0.0, _num(comp.get(e, 0.0))) for e in ELEMENTS}


def validate_composition(comp):
    comp = normalize_comp(comp)
    warnings = []
    typical = {
        'C': (0.05, 0.35), 'Si': (0.10, 0.80), 'Mn': (0.40, 1.80),
        'P': (0.0, 0.025), 'S': (0.0, 0.020), 'Cr': (0.0, 2.50),
        'Mo': (0.0, 0.80), 'Ni': (0.0, 5.00), 'Cu': (0.0, 0.60),
        'V': (0.0, 0.15), 'Nb': (0.0, 0.08), 'Ti': (0.0, 0.05),
        'Al': (0.0, 0.08), 'B': (0.0, 0.005), 'N': (0.0, 0.020)
    }
    for e, (lo, hi) in typical.items():
        if comp[e] < lo or comp[e] > hi:
            warnings.append(f"{e}={comp[e]:.4g}% 값이 일반 주강 설계 범위({lo}~{hi}%) 밖입니다.")
    if comp['P'] + comp['S'] > 0.035:
        warnings.append("P+S가 높아 저온 충격치와 연성이 급격히 저하될 수 있습니다.")
    if comp['B'] > 0.003 and comp['Ti'] < 3.4 * comp['N']:
        warnings.append("B 첨가 효과를 얻기에는 Ti/N 고정이 부족할 수 있습니다.")
    return warnings


def calculate_all_equivalents(comp):
    c = normalize_comp(comp)
    ceq_iiw = c['C'] + c['Mn']/6 + (c['Cr']+c['Mo']+c['V'])/5 + (c['Ni']+c['Cu'])/15
    ceq_jis = c['C'] + c['Mn']/6 + c['Si']/24 + c['Ni']/40 + c['Cr']/5 + c['Mo']/4 + c['V']/14
    pcm = c['C'] + c['Si']/30 + (c['Mn']+c['Cu']+c['Cr'])/20 + c['Ni']/60 + c['Mo']/15 + c['V']/10 + 5*c['B']
    cet = c['C'] + (c['Mn']+c['Mo'])/10 + (c['Cr']+c['Cu'])/20 + c['Ni']/40
    return {"ceq_iiw": round(ceq_iiw, 3), "ceq_jis": round(ceq_jis, 3), "pcm": round(pcm, 3), "cet": round(cet, 3)}


def calculate_ceq_by_standard(comp, standard="IIW (ASTM/ASME/EN)", **kwargs):
    r = calculate_all_equivalents(comp)
    if standard in ("IIW", "IIW (ASTM/ASME/EN)"):
        return "Ceq (IIW)", r['ceq_iiw']
    if standard == "JIS":
        return "Ceq (JIS)", r['ceq_jis']
    if standard in ("Pcm", "PCM", "Pcm (API/NORSOK)", "Pcm (Ito-Bessyo)"):
        return "Pcm (Ito-Bessyo)", r['pcm']
    if standard in ("CET", "CET (European)"):
        return "CET", r['cet']
    return "Ceq (IIW)", r['ceq_iiw']

# legacy names used by old main.py
def calculate_ceq(comp, standard="IIW"):
    return calculate_ceq_by_standard(comp, standard)[1]


def calculate_hjp(temp_c, time_hr_or_min, mode="Tempering"):
    # Hollomon-Jaffe parameter in conventional 10^-3 K(C+log t_hr) scale
    hours = max(1e-3, _num(time_hr_or_min, 1.0))
    if hours > 48:  # accept minutes from Streamlit inputs
        hours = hours / 60.0
    C = 20.0 if mode in ("Tempering", "S/R", "PWHT") else 18.0
    return ((_num(temp_c, 600) + 273.15) * (C + math.log10(hours))) / 1000.0


def _cooling_severity(cooling):
    text = str(cooling)
    if "수냉" in text or "Water" in text: return 1.00
    if "유냉" in text or "Oil" in text: return 0.72
    if "공냉" in text or "Air" in text: return 0.42
    if "노냉" in text or "Furnace" in text: return 0.18
    return 0.35


def _hardenability_index(c):
    # bounded empirical index for section-size sensitivity, not a real DI calculation
    idx = (1.8*c['C'] + 0.55*c['Mn'] + 0.75*c['Cr'] + 1.15*c['Mo'] +
           0.28*c['Ni'] + 0.18*c['Cu'] + 1.8*c['V'] + 2.5*c['B']*100)
    return max(0.15, min(5.0, idx))


def _ac3_estimate(c):
    return 910 - 203*math.sqrt(max(c['C'], 0.001)) - 15.2*c['Ni'] + 44.7*c['Si'] + 104*c['V'] + 31.5*c['Mo'] + 13.1*c['W'] if 'W' in c else 910 - 203*math.sqrt(max(c['C'], 0.001)) - 15.2*c['Ni'] + 44.7*c['Si'] + 104*c['V'] + 31.5*c['Mo']


def calculate_1st_stage_physics(comp, p1, thickness, **kwargs):
    c = normalize_comp(comp)
    thickness = max(1.0, _num(thickness, 150))
    p1 = p1 or {}
    mode = p1.get('type', p1.get('mode', 'Quenching'))
    temp = _num(p1.get('temp', 930), 930)
    time_min = max(1.0, _num(p1.get('time', 360), 360))
    severity = _cooling_severity(p1.get('cooling', p1.get('cool', '수냉(WQ)')))

    # solution/austenitizing factor with overheat penalty
    ac3 = _ac3_estimate(c)
    if mode == "Annealing":
        solution = 0.82
    elif temp < ac3 + 25:
        solution = max(0.78, 0.92 + (temp - (ac3 + 25)) * 0.002)
    else:
        solution = 1.0 - max(0.0, temp - 1050) * 0.00045
    solution = max(0.78, min(1.05, solution))

    # as-quenched/normalized tensile strength estimate before tempering
    chemistry_ts = (310 + 1250*c['C'] + 92*c['Si'] + 145*c['Mn'] + 105*c['Cr'] +
                    210*c['Mo'] + 42*c['Ni'] + 35*c['Cu'] + 520*c['V'] +
                    260*c['Nb'] + 150*c['Ti'] + 9000*c['B'])
    if mode == "Normalizing":
        mode_factor = 0.86
    elif mode == "Annealing":
        mode_factor = 0.70
    else:
        mode_factor = 1.03

    hidx = _hardenability_index(c)
    effective_depth = 45 + 110 * severity * hidx
    mass_effect = 0.58 + 0.42 / (1.0 + (thickness / max(20.0, effective_depth))**1.35)
    hold_factor = 1.0 - min(0.08, max(0, math.log10(time_min/240.0)) * 0.025)
    return max(250.0, chemistry_ts * mode_factor * solution * mass_effect * hold_factor)


def predict_microstructure(comp, p1, thickness, **kwargs):
    c = normalize_comp(comp)
    p1 = p1 or {}
    p_type = p1.get('type', p1.get('mode', 'Quenching'))
    severity = _cooling_severity(p1.get('cooling', p1.get('cool', '수냉(WQ)')))
    h = _hardenability_index(c)
    transform = severity * h / (1.0 + max(1.0, _num(thickness, 150))/180.0)
    if p_type == "Annealing":
        return "Ferrite + Coarse Pearlite (F+P)", "서냉/풀림 조건으로 조대한 페라이트·펄라이트 조직이 우세합니다."
    if p_type == "Normalizing":
        if transform > 0.75:
            return "Ferrite + Pearlite + Bainite (F+P+B)", "정규화 조직에 합금 경화능 영향으로 일부 베이나이트가 포함될 가능성이 있습니다."
        return "Ferrite + Pearlite (F+P)", "표준 정규화 조직으로 페라이트와 펄라이트가 주 조직입니다."
    if transform > 1.35:
        return "Tempered Martensite (TM)", "수냉 후 뜨임 시 예상되는 미세한 템퍼드 마르텐사이트 조직입니다."
    if transform > 0.75:
        return "Bainite + Tempered Martensite (B+TM)", "단면 두께와 냉각 속도 영향으로 베이나이트와 템퍼드 마르텐사이트 혼합 조직이 예상됩니다."
    if transform > 0.35:
        return "Bainite + Pearlite (B+P)", "질량 효과로 중심부 냉각 속도가 낮아져 베이나이트·펄라이트 혼합 조직이 예상됩니다."
    return "Ferrite + Pearlite (F+P)", "경화능 또는 냉각 속도가 낮아 페라이트·펄라이트 조직이 지배적입니다."


def get_final_expert_simulation(ts_1st, p2, p3, test_temp, comp, p1=None, thickness=150, ceq_standard="IIW (ASTM/ASME/EN)", p0=None, **kwargs):
    c = normalize_comp(comp)
    p2, p3 = p2 or {'type':'None','temp':0,'time':0,'cooling':'공냉(AC)'}, p3 or {'type':'None','temp':0,'time':0,'cooling':'공냉(AC)'}
    thickness = max(1.0, _num(thickness, 150))

    def temper_loss(p):
        mode = p.get('type', p.get('mode', 'None'))
        if mode == "None" or _num(p.get('time', 0)) <= 0:
            return 0.0
        hjp = calculate_hjp(p.get('temp', 600), p.get('time', 240), mode)
        if mode in ("Tempering", "S/R", "PWHT"):
            return max(0.02, min(0.38, (hjp - 14.0) * 0.040))
        if mode == "Annealing":
            return 0.30
        if mode == "Normalizing":
            return 0.08
        return 0.05

    loss = temper_loss(p2) + 0.65 * temper_loss(p3)
    cool_penalty = 0.96 if "노냉" in str(p2.get('cooling', p2.get('cool',''))) or "노냉" in str(p3.get('cooling', p3.get('cool',''))) else 1.0
    f_ts = max(300.0, _num(ts_1st, 500) * (1.0 - min(0.55, loss)) * cool_penalty)

    yr_base = 0.72 if not p1 or p1.get('type', p1.get('mode','')) != 'Quenching' else 0.82
    yr = min(0.94, yr_base + 0.035 * (temper_loss(p2) > 0.05) + 0.02*c['V']*10)
    f_ys = f_ts * yr

    p0_mode = (p0 or {}).get('type', (p0 or {}).get('mode', 'None'))
    grain_boost = 1.0 + (0.08 if p0_mode in ("Normalizing", "Homogenizing") else 0.0)

    f_el = max(4.0, (37.0 - 0.027*f_ts - 10.0*c['C'] + 2.0*c['Ni']) * grain_boost)
    f_ra = max(8.0, min(78.0, f_el*1.75 - 8.0*c['P']*100 - 10.0*c['S']*100))
    f_hb = max(90.0, f_ts / 3.30)

    # transition curve for Charpy; impurity and thickness effects included
    dbtt = -45 - 18*c['Ni'] - 18*c['Mn'] - 12*c['Mo'] + 80*c['C'] + 1450*c['P'] + 1900*c['S'] + 0.030*thickness
    upper = 135 + 28*c['Ni'] + 12*c['Mn'] + 10*c['Mo'] - 700*c['P'] - 1100*c['S'] - 0.030*max(0, thickness-100)
    upper = max(8.0, min(220.0, upper))
    cvn = 4.0 + (upper - 4.0) / (1.0 + math.exp(-0.075 * (_num(test_temp, -46) - dbtt)))
    if f_ts > 850:
        cvn *= max(0.65, 1.0 - (f_ts-850)/900)
    f_cvn = cvn * grain_boost

    ceq_label, ceq_val = calculate_ceq_by_standard(c, ceq_standard)
    micro_name, micro_desc = predict_microstructure(c, p1, thickness) if p1 else ("N/A", "공정 정보 부족으로 조직을 예측할 수 없습니다.")
    warnings = validate_composition(c)
    return {"ys":round(f_ys,1), "ts":round(f_ts,1), "el":round(f_el,1), "ra":round(f_ra,1), "hb":round(f_hb,1), "cvn":round(f_cvn,1),
            "ceq_val":ceq_val, "ceq_label":ceq_label, "ceq_all":calculate_all_equivalents(c), "micro_name":micro_name, "micro_desc":micro_desc,
            "warnings": warnings}

run_simulation_v6 = get_final_expert_simulation


def run_expert_inverse_engine(targets, **kwargs):
    t_ys = _num(targets.get('ys'), 485); t_ts = _num(targets.get('ts'), 625); t_cvn = _num(targets.get('cvn'), 27)
    t_el = _num(targets.get('el'), 18); t_ra = _num(targets.get('ra'), 35); t_hb = _num(targets.get('hb'), 190)
    t_temp = _num(targets.get('test_temp'), -46); thick = max(10.0, _num(targets.get('thick'), 150)); coupon_thick = max(10.0, _num(targets.get('coupon_thick'), 50))
    ceq_standard = targets.get('ceq_standard', 'IIW (ASTM/ASME/EN)')
    comments = []

    alloy = {"C":0.18,"Si":0.35,"Mn":1.25,"P":0.010,"S":0.005,"Cr":0.25,"Mo":0.08,"Ni":0.35,"Cu":0.10,"V":0.01,"Nb":0.00,"Ti":0.015,"Al":0.035,"B":0.0005,"N":0.008,"As":0.004,"Sn":0.004,"Sb":0.002,"Pb":0.001,"Zr":0.0}

    if thick > 120:
        alloy['Mn'] = 1.35; alloy['Cr'] = min(1.20, 0.25 + (thick-120)/650); alloy['Mo'] = min(0.45, 0.08 + (thick-120)/900)
        comments.append(f"두께 {thick:.0f}mm 질량 효과를 고려하여 Mn/Cr/Mo 경화능을 보강했습니다.")
    if t_ts > 700:
        alloy['V'] = 0.04; alloy['Nb'] = 0.015
        comments.append("고강도 목표로 V/Nb 미세합금화를 소량 반영했습니다.")
    if t_temp <= -80:
        alloy['Ni'] = min(5.0, 2.5 + t_cvn/55)
    elif t_temp <= -40:
        alloy['Ni'] = min(3.5, 0.8 + t_cvn/65)
    else:
        alloy['Ni'] = 0.25
    if alloy['Ni'] > 1.0:
        comments.append(f"저온 충격 요구를 고려하여 Ni 약 {alloy['Ni']:.2f}%를 제안했습니다.")

    p0 = {"mode":"None","temp":0,"time":0,"cool":"공냉(AC)"}
    if thick >= 220 or t_cvn >= 80:
        p0 = {"mode":"Normalizing","temp":930,"time":max(180, thick*1.6),"cool":"공냉(AC)"}
        comments.append("대형 단면/고충격 요구로 예비 Normalizing을 추천했습니다.")

    p1_temp = int(round((900 + 0.05*thick + 12*alloy['Cr'] + 18*alloy['Mo'])/5)*5)
    p1_temp = max(880, min(980, p1_temp))
    p1 = {"type":"Quenching" if t_ys >= 420 else "Normalizing", "temp":p1_temp, "time":max(180, thick*2.2), "cooling":"수냉(WQ)" if t_ys >= 460 else "공냉(AC)"}
    temper_temp = 640 if (t_el >= 23 or t_ra >= 50) else 610
    if t_ts > 760: temper_temp = 580
    p2 = {"type":"Tempering", "temp":temper_temp, "time":max(180, thick*1.2), "cooling":"공냉(AC)"}
    p3 = {"type":"S/R", "temp":610, "time":max(180, thick*0.8), "cooling":"노냉(FC)"}

    def solve_for_thickness(section):
        lo, hi = 0.06, 0.34
        best = alloy.copy()
        for _ in range(25):
            mid = (lo+hi)/2
            trial = alloy.copy(); trial['C'] = mid
            ts1 = calculate_1st_stage_physics(trial, p1, section)
            rep = get_final_expert_simulation(ts1, p2, p3, t_temp, trial, p1, section, p0={'type':p0['mode'],'temp':p0['temp'],'time':p0['time'],'cooling':p0['cool']})
            # satisfy TS/HB without sacrificing EL too much
            if rep['ts'] < t_ts or rep['hb'] < t_hb:
                lo = mid
            else:
                hi = mid
            best = trial
        best['C'] = round((lo+hi)/2, 3)
        return best

    alloy_coupon = solve_for_thickness(coupon_thick)
    alloy_prod = solve_for_thickness(thick)
    alloy = alloy_coupon.copy()

    p0_call = {'type':p0['mode'],'temp':p0['temp'],'time':p0['time'],'cooling':p0['cool']}
    coupon_rep = get_final_expert_simulation(calculate_1st_stage_physics(alloy_coupon,p1,coupon_thick), p2,p3,t_temp,alloy_coupon,p1,coupon_thick,p0=p0_call,ceq_standard=ceq_standard)
    prod_rep = get_final_expert_simulation(calculate_1st_stage_physics(alloy_prod,p1,thick), p2,p3,t_temp,alloy_prod,p1,thick,p0=p0_call,ceq_standard=ceq_standard)

    ceq_label, ceq_val = calculate_ceq_by_standard(alloy, ceq_standard)
    pcm = calculate_all_equivalents(alloy)['pcm']
    if ceq_val > 0.48: comments.append(f"주의: {ceq_label}={ceq_val}로 용접 예열/저수소 관리가 필요합니다.")
    if pcm > 0.25: comments.append(f"용접성 경고: Pcm={pcm}로 저온균열 민감도가 높습니다.")
    if coupon_rep['cvn'] < t_cvn or prod_rep['cvn'] < t_cvn:
        comments.append("목표 CVN 미달 가능성이 있습니다. P/S 저감, Ni 추가, 예비 Normalizing, 뜨임 조건 재검토가 필요합니다.")
    if coupon_rep['el'] < t_el or prod_rep['el'] < t_el:
        comments.append("목표 연성 미달 가능성이 있습니다. C 하향, 뜨임 온도 상향, 불순물 저감 검토가 필요합니다.")

    micro_name, micro_desc = predict_microstructure(alloy, p1, thick)
    ret_p1 = {"mode":p1['type'],"temp":p1['temp'],"time":p1['time'],"cool":p1['cooling']}
    ret_p2 = {"mode":p2['type'],"temp":p2['temp'],"time":p2['time'],"cool":p2['cooling']}
    ret_p3 = {"mode":p3['type'],"temp":p3['temp'],"time":p3['time'],"cool":p3['cooling']}
    comments.insert(0, "본 결과는 경험식 기반 1차 설계안이며 실제 적용 전 열처리 시험편/제품 부착 시험으로 보정해야 합니다.")
    return {"alloy":alloy,"alloy_coupon":alloy_coupon,"alloy_prod":alloy_prod,"p0":p0,"p1":ret_p1,"p2":ret_p2,"p3":ret_p3,
            "comments":comments,"ceq_val":ceq_val,"ceq_label":ceq_label,"ceq_all":calculate_all_equivalents(alloy),"micro_name":micro_name,"micro_desc":micro_desc,
            "coupon_rep":coupon_rep,"prod_rep":prod_rep}

run_inverse_v6 = run_expert_inverse_engine
