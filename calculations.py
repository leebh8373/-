import math

def calculate_alloy_factors(comp):
    c = comp.get('C', 0); mn = comp.get('Mn', 0); si = comp.get('Si', 0)
    cr = comp.get('Cr', 0); mo = comp.get('Mo', 0); v = comp.get('V', 0)
    ni = comp.get('Ni', 0); cu = comp.get('Cu', 0); b = comp.get('B', 0)
    
    # 1. PCM 계산
    pcm = c + si/30 + (mn + cu + cr)/20 + ni/60 + mo/15 + v/10 + 5*b
    
    # 2. 다양한 Ceq 규격 계산
    ceq_list = {
        'IIW (ASTM/ASME)': c + mn/6 + (cr + mo + v)/5 + (ni + cu)/15,
        'JIS (WES 3001)': c + mn/6 + si/24 + ni/40 + cr/5 + mo/4 + v/14,
        'AWS D1.1': c + (mn + si)/6 + (cr + mo + v)/5 + (ni + cu)/15,
        'EN ISO 15614': c + mn/6 + (cr + mo + v)/5 + (ni + cu)/15
    }
    return ceq_list, pcm

def calculate_hjp(temp_c, time_hr):
    if temp_c <= 0 or time_hr <= 0: return 0
    # Hollomon-Jaffe Parameter 수식
    return (temp_c + 273.15) * (20 + math.log10(time_hr)) / 1000

def calculate_combined_hjp(h_list):
    v_hjp = [h for h in h_list if h > 0]
    if not v_hjp: return 0
    # 다단 열처리 누적 효과 (경험적 보정 계수 0.12 적용)
    return max(v_hjp) + (sum(v_hjp) - max(v_hjp)) * 0.12