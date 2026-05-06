# Sentinel-Alpha 주강 물성 예측 시스템 정밀 분석 및 업그레이드 보고서

## 1. 확인된 주요 문제

### A. 실행 불능 문제
- `main.py`가 `calculations.py`에 존재하지 않는 `calculate_ceq`, `calculate_hjp` 함수를 import하고 있었습니다.
- `predictor.py`의 `predict_properties()` 함수는 7개 인자를 요구하지만, 기존 `main.py`는 3개 인자만 전달했습니다.
- 결과적으로 콘솔 버전은 실행 즉시 `ImportError` 또는 `TypeError`가 발생하는 구조였습니다.

### B. 예측 엔진의 물리/야금학적 문제
- 기존 강도식은 경험계수 위주이며, 일부 조건에서 비정상적으로 높은 강도 또는 충격치가 산출될 수 있었습니다.
- 질량 효과가 단순 보정으로 처리되어 두꺼운 주강품 중심부의 경화능 저하를 충분히 반영하지 못했습니다.
- CVN 예측에서 Ni 효과가 과도하여 저온 충격치가 비현실적으로 높게 산출될 수 있었습니다.
- 미세조직 예측이 CCT/경화능 개념보다 단순 임계값에 의존했습니다.

### C. 역설계 문제
- 목표 TS/HB를 맞추기 위해 C만 이분 탐색하는 구조라, 연성/충격/용접성과의 상충관계를 제대로 표시하지 못했습니다.
- 제품 본체와 시험편 조건은 비교하고 있으나, 미달 항목에 대한 경고가 부족했습니다.

## 2. 반영한 수정 및 업그레이드

### A. 호환성 복구
- `calculate_ceq()` 및 `calculate_hjp()` legacy 함수를 추가했습니다.
- `predictor.py` 함수 기본값을 보강하여 기존 호출 방식과 새 호출 방식 모두 대응하도록 수정했습니다.
- `main.py`의 import 및 함수 호출 오류를 수정했습니다.

### B. 예측 엔진 보강
- 성분 입력 정규화 및 범위 경고 기능을 추가했습니다.
- IIW/JIS/Pcm/CET 탄소당량 계산을 통합했습니다.
- 경화능 지수, 냉각 severity, 단면 두께를 이용한 질량 효과 모델로 변경했습니다.
- 오스테나이트화 온도 부족/과열 영향을 반영했습니다.
- 뜨임 및 S/R에 의한 강도 저하를 Hollomon-Jaffe parameter 기반으로 재구성했습니다.
- CVN 예측은 DBTT/upper shelf 형태의 전이곡선으로 변경했습니다.
- 조직 예측을 Ferrite/Pearlite/Bainite/Tempered Martensite 범주로 재정리했습니다.

### C. 역설계 엔진 보강
- 두께, 목표 강도, 저온 충격 요구를 기반으로 Mn/Cr/Mo/Ni/V/Nb를 제안하도록 수정했습니다.
- 시험편 기준과 제품 본체 기준을 각각 계산하여 비교합니다.
- Ceq/Pcm 과다, CVN 미달, 연성 미달 가능성을 코멘트로 표시합니다.

## 3. 사용상 중요 주의사항

본 프로그램은 설계 검토/사전 검토용 경험식 모델입니다. 실제 프로젝트 적용 시에는 다음으로 보정해야 합니다.

1. 실제 Heat별 화학성분과 열처리 차트
2. 제품 부착 시험편 또는 대표 시험편의 물성 결과
3. 주조 결함 수준, 보수용접 이력, 응고 조직, 두께별 냉각속도
4. ASTM/ASME/EN/ABS 등 적용 규격의 요구값

## 4. 수정 파일

- `calculations.py`: 핵심 예측/역설계 엔진 교체 및 호환 함수 추가
- `predictor.py`: 콘솔 호환 예측 함수 수정
- `main.py`: 실행 오류 수정
- `app.py`: 버전 표기 v6.4 반영

## v6.4.1 추가 업그레이드 (Mass Effect & Hardness Report)

### 요청 반영 사항
- 역설계 결과 화면에 두께별 물성 민감도 분석(Mass Effect Analysis)을 확장 적용했습니다.
- 역설계 교차검증 리포트에 브리넬 경도(HB)를 추가 표시했습니다.
- [Sentinel-Alpha 최종 기계적 물성 예측 리포트]의 경도 표시에 HB 단위를 명확히 추가했습니다.

### 역설계 Mass Effect Analysis 확장 내용
- 기존 TS/YS 중심 분석에서 아래 항목까지 확대했습니다.
  - 항복강도 YS
  - 인장강도 TS
  - 연신율 EL
  - 단면수축률 RA
  - 충격치 CVN
  - 브리넬 경도 HB
- Coupon 두께, 제품 본체 두께, 검토 최대 두께 기준의 물성 요약표를 추가했습니다.
- Coupon 대비 제품 본체의 TS/YS/CVN/HB 변화량을 별도 metric으로 표시하도록 했습니다.
- Plotly 사용 가능 시 강도/경도, 연성, 충격치 탭으로 나누어 그래프를 표시하도록 구성했습니다.

### 검증
- Python syntax compile 확인 완료: `python -S -m py_compile *.py`
- 계산 엔진 기본 호출 및 역설계 엔진 호출 확인 완료.


## v6.6.0 추가 업그레이드 - Excel/PDF 자동 실측 데이터 반영

### 1. Excel / CSV 자동 업로드
- `실측 데이터 누적/보정` 탭에서 `.xlsx`, `.xls`, `.csv` 업로드 지원
- Heat No., 재질, 제품명, 시험위치, 두께, 시험온도, 20원소 성분, 열처리 조건, 실측 YS/TS/EL/RA/CVN/HB 자동 매핑
- 표준 컬럼명 외에도 `YS`, `Yield Strength`, `항복강도`, `TS`, `UTS`, `인장강도`, `HB`, `Hardness`, `경도` 등 유사 컬럼명 인식

### 2. PDF 자동 추출
- `.pdf` MTR/기계시험 성적서 업로드 지원
- `pdfplumber` 기반 표 추출 우선 적용
- 표 추출 실패 시 PDF 텍스트에서 Heat No., 성분, 물성값을 정규식으로 보조 추출
- PDF 양식 편차에 따른 오인식 방지를 위해 `추출 미리보기 → 확인 후 DB 반영` 방식 적용

### 3. 누적 및 보정 자동 연결
- 업로드된 실측값은 현재 예측 엔진으로 재예측 후 `actual - predicted` 잔차로 저장
- 이후 예측 시 두께, Ceq, Pcm 유사도 기반 가중 잔차 보정에 자동 사용
- YS/TS/EL/RA/CVN/HB 전 항목에 보정값 반영

### 4. 업로드 템플릿 제공
- 탭 내 `Excel/CSV 업로드 템플릿 다운로드` 버튼 추가
- 사용자가 별도 양식 없이 표준 CSV 양식으로 실측 데이터를 정리 가능

### 5. 추가 의존성
- `openpyxl`: Excel 읽기
- `pdfplumber`, `pypdf`: PDF 표/텍스트 추출

## v6.6.1 추가 패치 — 업로드 파일 자동 추출 + 수동 두께 강제 적용

### 사용자 요청 반영
- Excel/PDF/CSV 업로드 파일에서는 Heat No., 재질/규격, 화학성분, 열처리 조건, 실측 기계적 물성(YS/TS/EL/RA/CVN/HB)을 자동 추출하도록 유지.
- 본품 두께 및 Coupon 두께는 업로드 파일에서 자동 추출하지 않고, 사용자가 별도로 입력한 값을 보정 DB에 강제 적용할 수 있도록 변경.

### 변경 내용
- 실측 데이터 누적/보정 탭의 업로드 영역에 다음 입력 필드 추가:
  - 업로드 데이터 본품 두께(mm)
  - 업로드 데이터 Coupon 두께(mm)
  - 파일 내 두께값 무시하고 위 두께 적용 체크박스
- 체크박스 ON 상태에서는 업로드 파일 내 Thickness/THK/두께 컬럼 또는 PDF 텍스트의 두께값을 무시하고, 수동 입력 두께를 모든 추출 행에 적용.
- 누적 DB note 필드에 `thickness_manual_override` 기록을 남겨 추적 가능하도록 개선.

### 목적
- MTR/PDF 성적서의 두께 표기가 제품 두께, 시험편 크기, 시험 위치 두께, 소재 두께 등으로 혼재될 수 있는 문제를 방지.
- Mass Effect 보정 모델에서 가장 중요한 두께 인자를 사용자가 직접 지정하여 보정 데이터 품질을 높임.

## v6.6.2 Patch - PDF/Excel 자동 반영 오류 수정

### 수정 배경
- 일부 PDF 성적서에서 표 구조는 후보 행으로 인식되지만, 기계적 물성값이 별도 텍스트 영역 또는 다른 표에 분리되어 있어 `보정 DB 반영 가능 0행`으로 표시되는 문제가 확인되었습니다.

### 조치 내용
- PDF 추출 로직을 `표 추출 + 본문 텍스트 추출` 병합 방식으로 변경했습니다.
- 표에서 Heat No. 또는 성분만 읽히고, 본문에서 YS/TS/EL/RA/CVN/HB가 읽히는 경우 하나의 DB 후보 행으로 병합합니다.
- PDF key-value 표, 화학성분 표, 기계시험 표 형태를 추가 인식하도록 보강했습니다.
- 보정 DB 반영 가능 행이 0건일 때는 CSV에 0건 저장으로 오인되지 않도록 오류 메시지를 표시하도록 변경했습니다.

### 사용 방법
1. PDF/Excel/CSV 파일 업로드
2. 본품 두께 및 Coupon 두께 입력
3. 추출 미리보기에서 실제 YS/TS/EL/RA/CVN/HB 값이 표시되는지 확인
4. `미리보기 데이터 누적 DB 반영` 클릭

> PDF가 스캔 이미지인 경우 OCR이 없으면 텍스트 추출이 제한됩니다. 이 경우 Excel/CSV 또는 텍스트 선택 가능한 PDF 사용을 권장합니다.

## v6.6.3 업데이트 - 이미지/스캔 PDF OCR 자동 인식 보강

### 개선 목적
- 기존 v6.6.2는 텍스트 선택 가능한 PDF 또는 PDF 내부 표 데이터 중심으로 추출했습니다.
- 이미지 스캔 PDF, 캡처 기반 PDF, 표가 이미지로 들어간 성적서는 `actual_ys`, `actual_ts`, `actual_el`, `actual_ra`, `actual_cvn`, `actual_hb` 값이 비어 보정 DB 반영이 되지 않을 수 있었습니다.

### 반영 사항
- PDF 직접 텍스트 추출 결과가 부족하거나, 기계적 물성 라벨이 충분히 보이지 않을 경우 OCR 보조 추출을 자동 실행하도록 수정했습니다.
- PyMuPDF로 PDF 페이지를 이미지로 렌더링하고, PIL 전처리 후 Tesseract OCR을 수행합니다.
- OCR 언어는 `eng+kor`를 우선 사용하며, 실패 시 `eng`로 fallback합니다.
- OCR 텍스트는 기존 PDF 텍스트와 병합되어 기존 성분/기계적 물성 파서에 그대로 연결됩니다.

### 추가 의존성
- PyMuPDF
- pytesseract
- Pillow

### 주의 사항
- OCR은 스캔 품질, 해상도, 표 선명도, 기울어짐, 도장/서명 겹침에 따라 오인식될 수 있습니다.
- DB 반영 전 추출 미리보기에서 Heat No., 성분, YS/TS/EL/RA/CVN/HB 값을 반드시 확인해야 합니다.
- 사용 PC에 Tesseract OCR 엔진이 설치되어 있어야 합니다. Python 패키지 `pytesseract`만으로는 OCR 엔진이 포함되지 않습니다.

## v6.6.4 - DAECHANG Material Certificate multi-cast parser fix

### Problem
- DCA-153-2 style Material Certificate has chemical composition, tensile/impact results, and heat-treatment records in separate table blocks.
- Generic PDF extraction merged table cells incorrectly, resulting in:
  - only 0~1 candidate row instead of 4 Cast No. rows,
  - Material Spec. misread or truncated,
  - Spec./Min. values sometimes confused with actual test values,
  - heat-treatment groups such as `No. 4` and `1,2,3` not expanded to each cast row.

### Fix
- Added `_parse_dca_material_certificate()` dedicated parser.
- The parser now extracts and expands:
  - Cast No. / Heat No.: ZJ296-6A, ZJ296-6B, ZJ296-6C, ZJ296-6D
  - Material Spec.: `ASTM A352 GR LCC with Purchase Spec.`
  - Product name: `HAWSE PIPE`
  - Chemical composition by each Cast No.
  - Tensile values by specimen: YS, TS, EL, RA
  - Impact average CVN by specimen
  - Heat Treatment groups into four rows:
    - No. 1,2,3: 903~910 / 900~908 / 640~650 / 608~610
    - No. 4: 910~920 / 895~903 / 635~645 / 608~610
- Heat-treatment hours are converted to minutes for the Sentinel calculation engine.

### Validation sample
- Tested with `Material Certificate_HAWSE PIPE.pdf`.
- Parser returns 4 rows, one row per Cast No./Specimen.


## v6.6.5 선택 삭제 기능 추가
- 실측 데이터 누적 DB 관리 영역에서 전체 초기화 버튼을 제거했습니다.
- 누적 DB 테이블에 `삭제 선택` 체크박스를 추가했습니다.
- 사용자가 선택한 행만 CSV DB에서 삭제하도록 구현했습니다.
- 내부 DB 행 번호를 보존하여 화면 정렬/표시와 무관하게 정확한 행이 삭제되도록 했습니다.
- 삭제 후 자동 새로고침(`st.rerun`)으로 화면에 즉시 반영되도록 했습니다.

## v6.6.6 PDF 이미지 업로드 / 선택 삭제 / Solution Heat Treatment 패치

### 목적
- v6.4 계열에서 가능했던 이미지/PDF 업로드 인식 흐름을 유지하면서, v6.6.5의 누적 DB 선택 삭제 기능과 대창 Material Certificate 전용 파서를 통합 안정화했습니다.
- 실측 데이터 입력 탭뿐 아니라 예측 시뮬레이션 공정 선택에도 1차 공정 `Solution Heat Treatment`를 추가했습니다.

### 주요 수정
1. PDF 업로드 UI/파서 재점검
   - 파일 업로더 허용 확장자: xlsx/xls/csv/pdf 유지 확인.
   - PDF 텍스트 추출 + OCR 보조 인식 + 대창 DCA Material Certificate 전용 파서 우선 적용 구조를 유지.
   - 대창 HAWSE PIPE Material Certificate 샘플 기준 Cast No. 4개가 각각 독립 보정 후보 행으로 생성되는지 검증.

2. 대창 Material Certificate 샘플 검증 결과
   - ZJ296-6A / ZJ296-6B / ZJ296-6C / ZJ296-6D 총 4행 정상 추출.
   - Material Spec.: ASTM A352 GR LCC with Purchase Spec. 정상 추출.
   - Product name: HAWSE PIPE 정상 추출.
   - Heat Treatment No. 1,2,3 그룹과 No. 4 그룹을 각 Cast No.에 자동 배정.
   - YS/TS/EL/RA/CVN AVG. 정상 추출.

3. 누적 DB 선택 삭제 재확인
   - 전체 초기화 버튼은 app.py에서 제거 상태 유지.
   - 누적 DB 테이블 앞에 삭제 선택 체크박스 표시.
   - 선택한 행의 내부 DB index 기준으로만 삭제.
   - 삭제 후 st.rerun()으로 즉시 화면 반영.

4. Solution Heat Treatment 추가
   - 정밀 물성 예측 시뮬레이션 탭의 1차 공정에 추가.
   - 실측 데이터 수동 입력 탭의 1차 공정에 추가.
   - PDF/Excel/CSV 자동 업로드 컬럼/별칭에서 solution heat treatment, solution treatment, SHT, 고용화, 용체화 인식 추가.
   - calculations.py에서 Solution Heat Treatment를 Quenching 계열과 유사한 1차 오스테나이트화/용체화 공정으로 반영.

### 검증
- app.py / calculations.py / predictor.py / main.py Python compile 완료.
- 샘플 PDF `Material Certificate_HAWSE PIPE(1).pdf` 기준 parse_pdf_certificate 결과 4행 확인.

## v6.6.7 Patch - DB 반영 즉시 갱신 및 중복 저장 방지
- 미리보기 데이터 누적 DB 반영 후 화면/건수 Metric이 즉시 갱신되도록 `st.rerun()` 및 flash message 구조를 추가했습니다.
- 같은 PDF/Excel/CSV를 반복 반영할 때 동일 레코드가 중복 누적되지 않도록 중복키 기반 병합 로직을 추가했습니다.
- 중복 판정은 timestamp, 예측값, 잔차, note를 제외하고 Heat No./재질/제품/두께/열처리/성분/실측값 기준으로 수행합니다.
- 수동 실측 입력 저장에도 동일한 중복 방지 로직을 적용했습니다.
- 선택 삭제 기능은 DB 내부 index 기준으로 유지되며, 삭제 후 즉시 새로고침됩니다.
