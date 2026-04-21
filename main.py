from calculations import calculate_ceq, calculate_hjp
from predictor import predict_properties

def main():
    print("=== 주강품 물성 예측 시스템 (Sentinel-Alpha Engine) ===")
    
    # 1. 화학 성분 입력 (기본값 설정)
    print("\n[1] 화학 성분 입력 (wt%)")
    c = float(input("C 함량: ") or 0.2)
    mn = float(input("Mn 함량: ") or 1.2)
    si = float(input("Si 함량: ") or 0.4)
    cr = float(input("Cr 함량: ") or 0.5)
    mo = float(input("Mo 함량: ") or 0.2)
    ni = float(input("Ni 함량: ") or 0.3)
    cu = float(input("Cu 함량: ") or 0.1)
    v = float(input("V 함량: ") or 0.01)
    
    chem_data = {'C': c, 'Mn': mn, 'Si': si, 'Cr': cr, 'Mo': mo, 'Ni': ni, 'Cu': cu, 'V': v}

    # 2. 규격 선택
    print("\n[2] 탄소당량(Ceq) 계산 규격 선택")
    print("1: IIW (Standard) | 2: JIS | 3: PCM (API/NORSOK)")
    choice = input("선택 (1-3, 기본값 1): ") or "1"
    std_map = {"1": "IIW", "2": "JIS", "3": "PCM"}
    selected_std = std_map.get(choice, "IIW")

    # 3. 열처리 및 제품 정보 입력
    print("\n[3] 열처리 및 제품 조건")
    t_temp = float(input("Tempering 온도 (°C): ") or 620)
    t_time = float(input("유지 시간 (hr): ") or 4)
    thickness = float(input("제품 유효 두께 (mm): ") or 100)

    # 4. 연산 실행
    ceq_val = calculate_ceq(chem_data, selected_std)
    hjp_val = calculate_hjp(t_temp, t_time)
    results = predict_properties(ceq_val, hjp_val, thickness)

    # 5. 결과 출력
    print("\n" + "="*50)
    print(f" 분석 규격: {selected_std}")
    print(f" 탄소당량 ({selected_std}): {ceq_val:.3f}")
    print(f" H-J Parameter: {hjp_val:.2f}")
    print("-" * 50)
    print(f" ▶ 예상 인장강도 (TS): {results['TS']} MPa")
    print(f" ▶ 예상 항복강도 (YS): {results['YS']} MPa")
    print(f" ▶ 예상 충격치 (CVN): {results['CVN']} J")
    print("-" * 50)

    # 6. 현장 조치 가이드 (상충 관계 분석)
    if results['TS'] < 485: # 예시 규격 하한치
        print("[조치 제안] 강도가 낮습니다. Ceq 상향 또는 Tempering 온도를 낮추십시오.")
    if results['CVN'] < 27:
        print("[조치 제안] 충격치가 불안합니다. 결정립 미세화 또는 냉각 속도를 점검하십시오.")
    print("="*50)

if __name__ == "__main__":
    main()