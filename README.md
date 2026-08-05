<p align="center">
  <img src="./icon.ico" alt="SBM4D 아이콘" width="96" />
</p>

<h1 align="center">SBM4D</h1>

<p align="center">
  <strong>SOOP BANNER MAKER FOR DAMBI</strong><br />
  SOOP 방송인 <a href="https://www.sooplive.com/station/cjstkdbsl3">깡담비</a>를 위한 하단 배너 이미지 자동 커터
</p>

## 소개

SBM4D는 정해진 규격의 이미지를 SOOP 하단 배너용 `720×150` PNG 파일로 자동 분할하는 Windows 데스크톱 도구입니다.

이미지 한 장을 선택하면 분할 위치와 출력 순서를 미리보기에서 확인할 수 있으며, 이미지 비율에 맞춰 프로그램 창 크기도 자동으로 조정됩니다. 이미지 처리는 Python과 [Pillow](https://python-pillow.org/)를 사용합니다.

## 주요 기능

- 한 장씩 선택하고 바로 처리하는 간단한 한국어 GUI
- 원본 이미지와 분할 위치를 보여주는 큰 미리보기
- 흰색 분할선과 `1~3` 또는 `1~6` 번호로 출력 순서 표시
- `720×450`, `1440×450` 입력 규격 자동 판별
- 이미지 비율에 맞춘 프로그램 창 크기 자동 조절
- 원본 파일명을 유지한 순번별 PNG 생성
- 기존 결과 파일 보호 및 덮어쓰기 확인
- 저장 위치 변경과 결과 폴더 바로 열기
- 여러 이미지를 처리할 수 있는 명령행 인터페이스
- 앱 아이콘이 포함된 Windows 단일 EXE 빌드

## 지원 규격

| 원본 이미지 | 분할 방식 | 결과 개수 | 결과 크기 |
| --- | --- | ---: | --- |
| `720×450` | 위에서 아래로 3등분 | 3개 | 각 `720×150` |
| `1440×450` | 왼쪽 위부터 오른쪽 아래까지 2열 × 3행 | 6개 | 각 `720×150` |

출력 파일은 원본 확장자를 제외한 이름을 기준으로 생성됩니다. 예를 들어 `banner.final.jpg`는 다음과 같이 저장됩니다.

```text
banner.final_1.png
banner.final_2.png
banner.final_3.png
...
banner.final_6.png
```

원본 이미지는 변경하지 않습니다. GUI에서 보이는 흰색 선과 번호도 미리보기 전용이며 결과 PNG에는 포함되지 않습니다.

선택 창에서는 PNG, JPG/JPEG, WebP, BMP, TIFF, GIF 파일을 열 수 있습니다. 움직이는 GIF나 다중 페이지 TIFF처럼 여러 프레임을 가진 이미지는 지원하지 않으며, 원본의 픽셀 크기가 위 규격과 정확히 일치해야 합니다.

## 일반 사용자용 EXE

빌드된 `SBM4D.exe`를 사용할 때는 파일 하나만 있으면 됩니다. Python, Pillow, `icon.ico` 또는 별도의 의존성 폴더를 설치하거나 함께 전달할 필요가 없습니다.

1. `SBM4D.exe`를 실행합니다.
2. `이미지 선택`을 눌러 원본 이미지 한 장을 고릅니다.
3. 미리보기, 원본 크기, 분할 가능 여부를 확인합니다.
4. 필요한 경우 `변경`을 눌러 저장 위치를 지정합니다.
5. `PNG로 자르기`를 누릅니다.
6. `결과 폴더 열기`에서 생성된 파일을 확인합니다.

저장 위치를 따로 선택하지 않으면 원본 이미지 옆의 `output` 폴더를 사용합니다. 작업이 끝난 뒤 `다른 이미지 선택`으로 같은 과정을 반복할 수 있습니다.

## Python으로 실행

Python 3.10 이상이 필요합니다.

```powershell
git clone https://github.com/uckdoman/SBM4D.git
cd SBM4D
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

또는 다음 명령으로도 실행할 수 있습니다.

```powershell
python -m sbm4d
```

인자 없이 실행하면 GUI가 열립니다.

## 명령행 사용

이미지 경로를 지정하면 GUI를 열지 않고 바로 처리합니다.

```powershell
python main.py "C:\images\banner.png" -o "C:\images\output"
```

여러 파일을 한 번에 처리할 수도 있습니다.

```powershell
python main.py `
  "C:\images\banner-a.png" `
  "C:\images\banner-b.png" `
  -o "C:\images\output"
```

`-o` 또는 `--output`을 생략하면 각 원본 이미지 옆의 `output` 폴더에 저장합니다. 기존 결과를 명시적으로 교체하려면 `--overwrite`를 추가합니다.

```powershell
python main.py "C:\images\banner.png" --overwrite
```

같은 저장 폴더에서 결과 파일명이 겹칠 입력은 원본 보호를 위해 처리하지 않습니다.

## Windows EXE 빌드

개발 의존성을 설치한 뒤 빌드 스크립트를 실행합니다.

```powershell
python -m pip install -r requirements-dev.txt
.\build_exe.ps1
```

완성된 단일 실행 파일은 다음 위치에 생성됩니다.

```text
dist\SBM4D.exe
```

빌드에는 저장소 루트의 `icon.ico`가 필요합니다. 이 아이콘은 EXE 파일과 프로그램 창에 함께 적용됩니다.

> 현재 빌드 스크립트는 디지털 코드 서명을 적용하지 않습니다. 배포 환경에 따라 Windows SmartScreen 알림이 나타날 수 있으며, 공개 배포 시에는 별도의 코드 서명 절차가 필요합니다.

## 테스트

```powershell
python -m unittest discover -s tests -v
```

현재 테스트는 이미지 분할, 출력 보호, 명령행 처리, 미리보기 좌표, 출력 번호 순서와 자동 창 크기 계산을 검증합니다.

## 프로젝트 구조

```text
SBM4D/
├─ main.py              # GUI 및 CLI 진입점
├─ icon.ico             # 앱 및 EXE 아이콘
├─ build_exe.ps1        # Windows 단일 EXE 빌드
├─ sbm4d/
│  ├─ cutter.py         # 이미지 분할 로직
│  ├─ gui.py            # Tkinter GUI
│  ├─ cli.py            # 명령행 인터페이스
│  └─ batch.py          # 여러 입력의 결과 충돌 검사
└─ tests/               # 자동 테스트
```
