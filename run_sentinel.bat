@echo off
title Sentinel-Alpha Quality System Launcher

:: [핵심] 네트워크 경로(UNC)를 가상 드라이브로 임시 할당합니다.
pushd "%~dp0"

echo [1/2] Checking Python Environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 파이썬이 설치되어 있지 않습니다. python.org에서 설치 후 실행해주세요.
    popd
    pause
    exit
)

echo [2/2] Installing/Updating Requirements...
:: 현재 폴더의 requirements.txt를 명확히 지정하여 설치합니다.
python -m pip install --upgrade pip --quiet
python -m pip install -r "%~dp0requirements.txt" --quiet

if %errorlevel% neq 0 (
    echo [ERROR] 라이브러리 설치 중 오류가 발생했습니다. 네트워크 연결을 확인하세요.
    popd
    pause
    exit
)

echo Starting Sentinel-Alpha Dashboard...
:: streamlit을 python 모듈 방식으로 실행하여 경로 문제를 원천 차단합니다.
start /b python -m streamlit run app.py --server.port 8501

echo.
echo ==========================================
echo 시스템이 실행되었습니다. 브라우저 창을 확인하세요.
echo 분석을 마친 후 이 창을 닫으면 종료됩니다.
echo ==========================================
pause

:: 프로그램 종료 시 가상 드라이브 할당을 해제합니다.
popd