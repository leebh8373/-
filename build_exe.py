import streamlit.web.cli as stcli
import os, sys

def resolve_path(path):
    basedir = getattr(sys, '_MEIPASS', os.getcwd())
    return os.path.join(basedir, path)

if __name__ == "__main__":
    # app.py가 메인 파일이라고 가정합니다.
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("app.py"), # 파일명이 다르면 수정하세요
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())