"""Compatibility predictor module for Sentinel-Alpha."""
from calculations import calculate_hjp


def predict_properties(ceq, pcm=0.25, combined_hjp=17.0, thickness=100, p_type="Normalizing", t_cool="공냉(AC)", extra_list=None):
    extra_list = extra_list or []
    factors = {'Annealing':0.78, 'Normalizing':1.0, 'Solution Annealing':0.85, 'Quenching (Oil)':1.25, 'Quenching (Water)':1.42}
    f_base = factors.get(p_type, 1.0)
    f_cool = 0.96 if "노냉" in t_cool else 1.0
    mass_effect = max(0.55, 1 - (float(thickness) / 1800))
    softening = max(0, float(combined_hjp) - 14.2) * 42
    ts = (float(ceq)*780 + float(pcm)*300 - softening + 260) * f_base * f_cool * mass_effect
    ys = ts * (0.84 if 'Quenching' in p_type else 0.73)
    el = 42 - (ts / 28) + (float(combined_hjp) * 0.55)
    ra = el * 1.7
    hb = ts / 3.3
    cvn_penalty = 0.82 if "노냉" in t_cool else 1.0
    cvn = ((float(combined_hjp)*12) - (float(ceq)*75) + (100/(float(thickness)**0.5))) * cvn_penalty
    rs = 380 if 'Quenching' in p_type else 160
    if 'S/R' in extra_list: rs *= 0.25
    if 'PWHT' in extra_list: rs *= 0.12
    return {'TS':round(max(ts,300),1),'YS':round(max(ys,220),1),'EL':round(max(el,4),1),'RA':round(max(ra,8),1),'CVN':round(max(cvn,2),1),'HB':round(max(hb,90),0),'RS':round(rs,1)}


def suggest_heat_treatment(ceq, target_ts, target_cvn, thickness):
    primary = "Quenching (Water)" if target_ts > 680 else "Normalizing"
    req_hjp = 15.5 + (float(ceq)*650 + 260 - float(target_ts)) / 70
    temp = (max(14.5, min(19.0, req_hjp)) * 1000 / 20.0) - 273.15
    return {'primary': primary, 'temp': round(temp, 0), 'time': 4.0, 'cooling': '공냉(AC)'}
