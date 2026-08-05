# SBM4D

**SOOP BANNER MAKER FOR DAMBI**

SOOP 방송인 [깡담비](https://www.sooplive.com/station/cjstkdbsl3)를 위해 만든 하단 배너 이미지 자동 커터입니다.

Python과 [Pillow](https://python-pillow.org/)를 사용하며, 입력 이미지 규격을 자동으로 판별해 배너별 PNG 파일로 저장합니다.

## 주요 기능

- `720×450`, `1440×450` 이미지 자동 판별
- 여러 이미지 일괄 처리
- 원본 파일명을 유지한 순번별 PNG 출력
- Windows용 한국어 GUI와 명령행 실행 지원

## 설치

Python 3.10 이상이 필요합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## GUI 실행

```powershell
python main.py
```

이미지를 선택하고 저장 폴더를 확인한 다음 `이미지 자동 자르기`를 누르시면 됩니다. 처음 이미지를 선택하면 해당 이미지 옆의 `output` 폴더가 기본 저장 위치로 지정됩니다.

## 명령행 실행

```powershell
python main.py "C:\images\banner.png" -o "C:\images\output"
```

여러 파일도 한 번에 지정할 수 있습니다.

```powershell
python main.py "C:\images\banner-a.png" "C:\images\banner-b.png" -o "C:\images\output"
```

결과 파일은 `원본파일명_1.png` 형식으로 생성됩니다.

기존 결과 파일은 기본적으로 보호됩니다. GUI에서는 덮어쓰기 여부를 묻고, 명령행에서는 필요한 경우에만 `--overwrite` 옵션을 사용하실 수 있습니다. 같은 저장 폴더에서 결과 이름이 겹칠 입력 파일은 안전을 위해 처리하지 않습니다.

## Windows 실행 파일 만들기

개발 환경에서 일반 사용자용 단일 실행 파일을 만들 수 있습니다.

```powershell
python -m pip install -r requirements-dev.txt
.\build_exe.ps1
```

완성된 파일은 `dist\SBM4D.exe`에 생성됩니다.

## 테스트

```powershell
python -m unittest discover -s tests -v
```
