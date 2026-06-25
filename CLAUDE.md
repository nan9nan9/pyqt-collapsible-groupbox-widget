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
`setAnimationDuration/animationDuration`, `setArrowColor`, `setArrowStyle`, `setArrowSize`, `setTitle`(일반/HTML),
`setSummaryEnabled/setSummary/setSummaryPosition/summaryLabel`,
시그널 `collapsedChanged(bool)`.

---

## 패키지 구조

```
src/collapsible_groupbox/
├── __init__.py               # 공개 API (CollapsibleGroupBox)
├── collapsible_group_box.py  # 위젯 본체 (전체 구현이 이 한 파일)
└── py.typed
examples/  basic_example.py, embed_in_your_app.py
tests/     test_collapsible.py  (pytest + offscreen, 54개)
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
- **화살표 회전/모핑 애니메이션**: `arrowProgress` Qt 프로퍼티(0=접힘 ~ 1=펼침)를
  `QPropertyAnimation` 으로 구동, setter 가 `update()` 호출 → `paintEvent`→`_draw_arrow` 가
  스타일별로 다시 그린다. 색은 `setArrowColor` 또는 팔레트 글자색.
- **아이콘 스타일 옵션**: `setArrowStyle(...)` (목록·검증은 `arrowStyles()`, 상수는 클래스
  속성). `_draw_arrow` 가 분기: `_draw_chevron`(폴리라인, 회전 `-90°*(1-progress)`),
  `_draw_triangle`(채워진 삼각형, 같은 회전), `_draw_plus_minus`(가로선 고정 + 세로선 길이를
  `(1-progress)` 로 모핑 → +↔−). 선 펜은 `_stroke_pen` 공용 헬퍼.
- **아이콘 크기**: `_arrow_size()` 는 `_arrow_size_override`(있으면) 우선, 없으면 폰트 기준
  (`fontMetrics*0.62`, 하한 9). `setArrowSize(px|None)` 로 인스턴스별 조절(크기가 들여쓰기·sizeHint
  에 영향하므로 `_refresh_title`+`updateGeometry`). 전역 기본값은 환경변수 `COLLAPSIBLE_ARROW_SIZE`
  (`_env_arrow_size()`, 숫자 아니면 무시) — simeditor 의 `$SIMEDITOR_*` 패턴과 동일.
- **HTML 리치텍스트 제목**: `setTitle` 이 `Qt.mightBeRichText` 로 HTML 여부를 자동 감지한다
  (`_is_rich`). plain 이면 위 네이티브 경로 그대로. rich 이면 네이티브 제목은 자리(들여쓰기
  공백)만 두고, `paintEvent`→`_draw_rich_title` 가 `QTextDocument`(캐시 `_title_doc`,
  `setHtml`)로 라벨 위치에 직접 그린다(배경 `fillRect(Window)` 로 네이티브 잔상·프레임 선 지운
  뒤 얹음, 색 미지정 부분은 `painter.setPen(글자색)`). 폭은 `_expand_hint_width` 가 rich 분기로
  `label.left()+indent+doc.idealWidth()+pad` 를 보장(rich 는 말줄임 없음 — 좁으면 우측 클립).
  폰트 변경 시 `changeEvent` 가 `_title_doc=None` 으로 무효화. `title()` 은 HTML 원본 반환.
- **제목 잘림 방지**: 화살표 들여쓰기가 제목 폭을 ~25px 늘려 좁은 폭에서 끝 글자가
  잘리던 문제를 두 가지로 막는다. (1) `minimumSizeHint()`/`sizeHint()` 를 오버라이드해
  "전체 제목(들여쓰기 포함) + 우측 여백(`_title_right_pad`)" 폭을 항상 보장한다. (2) 그래도
  폭이 부족하면 하드 클립 대신 `QFontMetrics.elidedText` 로 말줄임(…) 한다(`_apply_display_title`,
  `resizeEvent`/`showEvent` 에서 재계산, `_applying_title` 재귀 가드). 표시 제목이 말줄임돼도
  `minimumSizeHint` 는 전체 제목 기준이라 폭이 줄어드는 피드백 루프가 없다. `title()` 은 항상
  말줄임 없는 순수 제목을 돌려준다(라벨 rect 자체는 스타일이 잉크폭에 맞추므로 바닐라
  QGroupBox 와 동일하게 ~1–2px 빠듯할 수 있으나, 이는 폭 충분 시 시각적으로 문제없음).
- **접기 토글 트리거**: 별도 버튼/체크박스 대신 **제목 줄 전체 클릭**. `_header_hit` 은
  글자 라벨만이 아니라 `0 <= y <= _header_height()` 인 가로 전체를 헤더로 본다(빈 영역도 토글).
  `mouseMoveEvent`/`leaveEvent` 로 헤더 위에서만 `PointingHandCursor` 를 띄우고 벗어나면
  `unsetCursor`(상태는 `_hover_cursor` 로 추적, `setMouseTracking(True)` 필요).
  `setCheckable(True)` 와 공존하도록 체크박스 인디케이터(`SC_GroupBoxCheckBox`) 위 클릭/hover 는
  QGroupBox 의 체크 토글로 양보한다.
- **요약 라벨**: `setSummaryEnabled(bool)`/`setSummary(text)` 로 켜면 `QLabel`(`_summary_label`,
  자식)로 요약을 보여준다(표시 시점은 아래 "요약 표시 모드"). 마우스는 `WA_TransparentForMouseEvents`
  로 통과시켜 헤더 클릭 토글을 유지하고, 기본색은 팔레트 글자색 alpha 150이며 `summaryLabel()`
  로 커스터마이즈한다. `_content_children()` 에서 제외(접기/펴기 hide 대상 아님).
  `_after_collapse`/`_do_expand`/`resizeEvent`/`showEvent` 에서 `_update_summary_label` 로 갱신,
  비활성·빈 텍스트·공간 부족(<16px)·표시 조건 미충족이면 숨긴다.
- **요약 표시 모드**: `setSummaryPosition(SummaryBeside|SummaryInside|SummaryAlways)` (상수는 클래스 속성).
  - `SummaryBeside`(기본): 접힘일 때만 제목 오른쪽(`_title_right_edge` 옆, 라벨 rect 와 같은 줄).
  - `SummaryInside`: 접힘일 때만 박스 안쪽(접힌 높이 `_header_height` 에 `_summary_line_height`
    를 더하고 `y=_title_band_height`, 프레임 안쪽 x).
  - `SummaryAlways`: 펼침·접힘 모두 제목 오른쪽(콘텐츠를 가리지 않도록 펼침에서도 Beside 위치).
  - 표시 판정은 `_update_summary_label` 에서 `enabled & text & (collapsed or mode==Always)`.
    Inside 의 박스안쪽 배치는 `collapsed` 일 때만(펼침이면 Beside 위치로 fallback).
  - 헤더 띠/제목 시작점은 `_title_band()`(네이티브 라벨 rect)·`_title_left()`·`_title_band_height()`
    로 계산하고 화살표/요약/sizeHint 가 공유한다. 화살표·옆 요약은 라벨 rect 세로 중앙에 맞춘다.
  - **제목 위치 자체는 옵션으로 제공하지 않는다**(과거 TitleAbove 실험은 제거됨). 제목은 네이티브
    QGroupBox 렌더링을 그대로 쓰므로, 위치/스타일은 `QGroupBox::title { ... }` 스타일시트로 조정한다.
- **애니메이션 수명 관리**: `_start_animation(attr, prop, ...)` 공통 헬퍼가 이전 애니메이션을
  `stop()+deleteLater()` 로 수거하고 종료 시에도 `deleteLater` 한다. (parent=self 로 만든
  QPropertyAnimation 을 정리 안 하면 토글마다 자식으로 쌓여 누수 — 회귀 테스트 있음.)
- **폰트/스타일/활성 변화 대응**: `changeEvent` 에서 `FontChange`/`StyleChange` 시 들여쓰기·
  화살표·라벨 위치를 다시 계산하고, `EnabledChange` 시 화살표 색(비활성이면 `QPalette.Disabled`
  글자색)을 다시 그린다. `resizeEvent` 는 **폭이 바뀐 경우에만** 말줄임을 재계산(높이만 바뀌는
  접기 애니에서 매 프레임 `setTitle` 왕복 방지). `setArrowColor` 는 `QColor`/색문자열 모두 허용.
- **높이 접기**: `boxHeight` Qt 프로퍼티(`setMinimumHeight`+`setMaximumHeight` 동시 설정)를
  `QPropertyAnimation` 으로 구동한다. min/max 를 함께 고정해야 자식 위젯이 만든 레이아웃
  최소높이를 무시하고 헤더 높이까지 줄일 수 있다. 접힘 끝나면 자식을 `hide()`(원래 보였던
  것만 기억해 복원), 펼침 끝나면 min/max 제약을 풀어(`_saved_min`, `_QWIDGETSIZE_MAX`)
  레이아웃이 자연 크기를 정하게 한다.
- **접힘 높이(`_header_height`)**: `_title_band_height()`(라벨/체크박스 bottom+프레임폭,
  `fontMetrics+6` 하한) + (SummaryInside 활성 시 `_summary_line_height`).
- **애니메이션 off / 비표시 상태**: `setAnimated(False)` 또는 `isVisible()==False` 면 즉시 반영.

`_QWIDGETSIZE_MAX = 16777215` 은 qtpy 미노출이라 직접 정의(Qt 공통값).

---

## 작업 규칙 / 컨벤션

- **언어**: 응답·주석·커밋·문서 한국어, 코드 식별자 영어. 들여쓰기 4칸.
- **테스트**: `tests/`(pytest). 헤드리스: `QT_QPA_PLATFORM=offscreen python3 -m pytest -q`.
  `pyproject.toml` 의 `pythonpath=src` 로 설치 없이 동작. **현재 54개 통과 기준** — 변경 시 회귀 추가.
- **검증 루틴**: 수정 후 `py_compile` + 전체 pytest 통과 확인.
- **GUI 확인**: offscreen 으로 `widget.grab().save(png)` 캡처해 검토.
- **호환성 주의**: 새 Qt enum/메서드 사용 시 Qt5/Qt6 양쪽 동작 확인(필요하면 헬퍼로 흡수).
