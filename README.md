# pyqt-collapsible-groupbox-widget

제목을 클릭하면 **접고 펼 수 있는** `QGroupBox` 위젯.
기존 `QGroupBox` 와 API 가 호환되며, 추가되는 것은 **접기/펴기 기능 하나**뿐이다.

- 접으면 제목 줄만 남고 내부 콘텐츠는 모두 감춰진다.
- 제목 앞에 셰브론 화살표를 직접 그려(안티앨리어싱) 상태를 보여준다.
  펼치면 아래(˅), 접으면 오른쪽(›)으로 부드럽게 **회전**한다.
- 제목 영역을 클릭하면 토글된다(별도 버튼 불필요).
- 펼침/접힘은 부드러운 애니메이션으로 처리된다(끌 수 있음).
- **qtpy** 추상화로 **PyQt5 / PyQt6 / PySide2 / PySide6** 모두에서 동작한다.

![demo](docs/demo.png)

## 설치

```bash
pip install -e .
# Qt 바인딩은 택1로 별도 설치 (qtpy 가 자동 감지)
pip install PyQt5      # 또는 PySide6 / PySide2 / PyQt6
```

`src-layout` 패키지다. import 이름은 `collapsible_groupbox`, 배포 이름은 `pyqt-collapsible-groupbox-widget`.

## 사용법

기존 `QGroupBox` 를 쓰던 코드에서 **클래스 이름만 바꾸면** 된다.

```python
from collapsible_groupbox import CollapsibleGroupBox
from qtpy.QtWidgets import QVBoxLayout, QCheckBox

box = CollapsibleGroupBox("옵션")        # QGroupBox 대신 이것만
layout = QVBoxLayout(box)
layout.addWidget(QCheckBox("자동 저장"))

box.setCollapsed(True)                    # 접어 두고 시작
box.collapsedChanged.connect(print)       # 상태 변화 알림

# 제목에 HTML(리치텍스트)도 가능 — 자동 감지된다
box.setTitle("<b>설정</b> <font color='#e67e22'>●</font> 고급")
```

제목 줄(글자뿐 아니라 빈 영역 포함) 어디를 클릭해도 토글되며, 그 위에서는 손가락 커서가 뜬다.

## 공개 API

`CollapsibleGroupBox` 는 `QGroupBox` 의 모든 API(`setTitle`/`title`/`setLayout`/
`setCheckable`/`setFlat` …)를 그대로 지원한다. 추가된 멤버는 다음과 같다.

| 멤버 | 설명 |
|---|---|
| `setCollapsed(bool)` / `isCollapsed()` | 접힘 상태 설정/조회 |
| `collapsed` (Qt 프로퍼티) | Qt Designer·스타일시트용 bool 프로퍼티 |
| `collapse()` / `expand()` / `toggleCollapsed()` | 접기 / 펴기 / 토글 |
| `setCollapsible(bool)` / `isCollapsible()` | 접기 기능 on/off (off 면 항상 펼침 고정) |
| `setAnimated(bool)` / `isAnimated()` | 애니메이션 사용 여부 (기본 True) |
| `setAnimationDuration(ms)` / `animationDuration()` | 애니메이션 길이 (기본 180ms) |
| `setArrowColor(color)` | 화살표 색 지정 (`QColor`/`"red"`/`"#3498db"`, `None`=글자색) |
| `setTitle(text)` | 일반 텍스트 또는 **HTML**(`<b>`, `<font color>` 등) 지원 |
| `collapsedChanged(bool)` 시그널 | 접힘 상태가 바뀔 때 발생 (True=접힘) |

> `title()` 은 `setTitle` 에 넣은 **원본**을 그대로 반환한다(HTML 이면 HTML, 화살표 들여쓰기 제외).
> 좁은 폭에서 일반 제목은 말줄임(…)으로, HTML 제목은 폭이 부족하면 우측이 잘린다.

## 예제

```bash
python3 examples/basic_example.py        # 여러 그룹 + 외부 토글 버튼
python3 examples/embed_in_your_app.py     # 기존 앱 임베드 최소 예제
```

## 테스트

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest -q
```

## 라이선스

GPL-2.0-or-later
# pyqt-collapsible-groupbox-widget
