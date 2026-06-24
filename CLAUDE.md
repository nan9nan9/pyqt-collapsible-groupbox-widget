# collapsible_groupbox — 접이식 QGroupBox 위젯

`QGroupBox` 를 상속해 "접기/펴기" 기능만 추가한 재사용 위젯 패키지.
다른 Qt 프로그램에서 `from collapsible_groupbox import CollapsibleGroupBox` 한 줄로
임베드한다. 기존 `QGroupBox` 코드에서 클래스명만 바꾸면 그대로 동작한다.

---

## 기술 스택 / 호환성

- **Python 3.8+** (`from __future__ import annotations` 로 하위호환).
- **qtpy 추상화** — 호스트의 Qt 바인딩(PySide2 / PySide6 / PyQt5 / PyQt6)을 자동 감지.
  - **unscoped Qt enum** 사용: `Qt.LeftButton`, `QStyle.CC_GroupBox`,
    `QStyle.SC_GroupBoxLabel` (Qt5/Qt6 공통). scoped 형태(`Qt.MouseButton.LeftButton`) 금지.
  - `app.exec_()` 사용(전 바인딩 공통).
  - Qt6/Qt5 차이가 있는 API 는 헬퍼로 흡수: `_event_point()`(마우스 좌표 `position()` vs `pos()`).
- **src-layout 패키지**: import 이름 `collapsible_groupbox`, 배포 이름 `pyqt-collapsible-groupbox-widget`.

---

## 공개 API (진입점)

```python
from collapsible_groupbox import CollapsibleGroupBox
box = CollapsibleGroupBox("옵션")     # QGroupBox 처럼 사용
box.setCollapsed(True)
```

`QGroupBox` 의 모든 API 호환. 추가 멤버:
`setCollapsed/isCollapsed`, `collapsed`(Qt 프로퍼티), `collapse/expand/toggleCollapsed`,
`setCollapsible/isCollapsible`, `setAnimated/isAnimated`,
`setAnimationDuration/animationDuration`, `setArrowColor`, 시그널 `collapsedChanged(bool)`.

---

## 패키지 구조

```
src/collapsible_groupbox/
├── __init__.py               # 공개 API (CollapsibleGroupBox)
├── collapsible_group_box.py  # 위젯 본체 (전체 구현이 이 한 파일)
└── py.typed
examples/  basic_example.py, embed_in_your_app.py
tests/     test_collapsible.py  (pytest + offscreen, 15개)
docs/      demo.png
```

---

## 구현 핵심 (이 범위 내에서만 작업)

- **타이틀 + 직접 그린 화살표**: `setTitle()`/`title()` 을 오버라이드해 사용자 제목은
  `self._title` 에 보관하고, 화면 표시용으로는 `super().setTitle(공백들여쓰기 + 제목)` 처럼
  앞에 공백을 넣어 화살표를 그릴 자리만 비운다(`_title_indent`, 폰트 기준 공백폭 계산 —
  Qt6 `horizontalAdvance`/Qt5 `width`). 화살표 자체는 `paintEvent` 에서 `QPainter` 로
  안티앨리어싱 셰브론(˅)을 직접 그린다(유니코드 ▼/▶ 는 폰트 의존적이라 폐기). 그래서
  `title()` 은 들여쓰기 없는 순수 제목을 돌려준다. 생성자 제목은 C++ 경로라 우리
  오버라이드를 안 거치므로 `__init__` 에서 `super().title()` 로 회수한다.
- **화살표 회전 애니메이션**: `arrowProgress` Qt 프로퍼티(0=접힘 › ~ 1=펼침 ˅)를
  `QPropertyAnimation` 으로 구동, setter 가 `update()` 호출 → `paintEvent` 가 회전각
  `-90°*(1-progress)` 로 셰브론을 다시 그린다. 색은 `setArrowColor` 또는 팔레트 글자색.
- **접기 토글 트리거**: 별도 버튼/체크박스 대신 **타이틀 영역 클릭**. `mousePressEvent` 에서
  `QStyle.subControlRect(CC_GroupBox, opt, SC_GroupBoxLabel)` 로 라벨 영역을 구해 hit-test.
  `setCheckable(True)` 와 공존하도록 체크박스 인디케이터(`SC_GroupBoxCheckBox`) 위 클릭은
  QGroupBox 의 체크 토글로 양보한다.
- **높이 접기**: `boxHeight` Qt 프로퍼티(`setMinimumHeight`+`setMaximumHeight` 동시 설정)를
  `QPropertyAnimation` 으로 구동한다. min/max 를 함께 고정해야 자식 위젯이 만든 레이아웃
  최소높이를 무시하고 헤더 높이까지 줄일 수 있다. 접힘 끝나면 자식을 `hide()`(원래 보였던
  것만 기억해 복원), 펼침 끝나면 min/max 제약을 풀어(`_saved_min`, `_QWIDGETSIZE_MAX`)
  레이아웃이 자연 크기를 정하게 한다.
- **접힘 높이(`_header_height`)**: `SC_GroupBoxLabel`/`SC_GroupBoxCheckBox` rect 의 bottom +
  프레임 폭으로 계산, `fontMetrics().height()+6` 하한.
- **애니메이션 off / 비표시 상태**: `setAnimated(False)` 또는 `isVisible()==False` 면 즉시 반영.

`_QWIDGETSIZE_MAX = 16777215` 은 qtpy 미노출이라 직접 정의(Qt 공통값).

---

## 작업 규칙 / 컨벤션

- **언어**: 응답·주석·커밋·문서 한국어, 코드 식별자 영어. 들여쓰기 4칸.
- **테스트**: `tests/`(pytest). 헤드리스: `QT_QPA_PLATFORM=offscreen python3 -m pytest -q`.
  `pyproject.toml` 의 `pythonpath=src` 로 설치 없이 동작. **현재 15개 통과 기준** — 변경 시 회귀 추가.
- **검증 루틴**: 수정 후 `py_compile` + 전체 pytest 통과 확인.
- **GUI 확인**: offscreen 으로 `widget.grab().save(png)` 캡처해 검토.
- **호환성 주의**: 새 Qt enum/메서드 사용 시 Qt5/Qt6 양쪽 동작 확인(필요하면 헬퍼로 흡수).
