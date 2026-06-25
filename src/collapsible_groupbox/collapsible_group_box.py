"""접을 수 있는(collapsible) QGroupBox 위젯 (qtpy 추상화).

`QGroupBox` 를 그대로 상속하므로 기존 QGroupBox API 와 100% 호환된다.
추가되는 기능은 "접기/펴기" 단 하나다:

- 제목(타이틀) 영역을 클릭하면 접히거나 펴진다.
- 제목 앞에 셰브론(˅) 화살표를 직접 그려 현재 상태를 알려준다.
  접으면 오른쪽(›), 펴면 아래(˅)로 부드럽게 회전한다.
- 접히면 제목 줄만 남고 내부 콘텐츠는 모두 감춰진다(높이도 줄어든다).
- 펴고 접는 과정은 부드러운 애니메이션으로 처리된다(끌 수 있음).

다른 프로그램에서는 기존 `QGroupBox` 를 쓰던 코드를 그대로 두고
클래스만 `CollapsibleGroupBox` 로 바꾸면 된다.
"""

from __future__ import annotations

import os

from qtpy.QtCore import (
    Qt, Signal, Property, QPropertyAnimation, QEasingCurve,
    QRectF, QPointF, QSize, QEvent, QByteArray,
)
from qtpy.QtGui import QPainter, QPen, QPolygonF, QPalette, QColor, QTextDocument
from qtpy.QtWidgets import (
    QGroupBox,
    QWidget,
    QLabel,
    QStyle,
    QStyleOptionGroupBox,
)

# QtSvg 는 별도 모듈이라 없을 수도 있다(없으면 SVG 아이콘은 셰브론으로 graceful fallback).
try:
    from qtpy.QtSvg import QSvgRenderer
    _HAS_SVG = True
except Exception:  # pragma: no cover - QtSvg 미설치 환경 대비
    QSvgRenderer = None
    _HAS_SVG = False

# QWidget 의 "무제한 높이" 상수. qtpy 가 노출하지 않으므로 직접 정의한다(Qt 공통값).
_QWIDGETSIZE_MAX = 16777215


def _event_point(event):
    """마우스 이벤트의 위젯 좌표를 QPoint 로 반환한다.

    Qt6 는 position().toPoint(), Qt5 는 pos() 를 쓴다(qtpy 가 통일해 주지 않음).
    """
    pos_fn = getattr(event, "position", None)
    if pos_fn is not None:
        return pos_fn().toPoint()
    return event.pos()


def _might_be_rich(text):
    """제목 문자열이 HTML 리치텍스트로 보이는지 판정한다(plain 이면 기존 경로 유지)."""
    fn = getattr(Qt, "mightBeRichText", None)
    return bool(fn(text)) if fn is not None else ("<" in text and ">" in text)


# 화살표 기본 크기를 OS 환경변수로 덮어쓸 수 있다(simeditor 의 $SIMEDITOR_* 패턴과 동일).
#   COLLAPSIBLE_ARROW_SIZE=18  → 모든 위젯의 기본 화살표 크기(px)
# 인스턴스별로는 setArrowSize() 로 따로 조절한다.
ARROW_SIZE_ENV = "COLLAPSIBLE_ARROW_SIZE"


def _env_arrow_size():
    raw = os.environ.get(ARROW_SIZE_ENV)
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return None


# SVG 아이콘: 파일은 assets/ 에 번들한다. fill/stroke="currentColor" 를 글자색으로 치환해 쓴다.
_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
_svg_text_cache = {}       # filename -> svg 원본 텍스트
_svg_renderer_cache = {}   # (filename, color_hex) -> QSvgRenderer


def _svg_text(filename):
    text = _svg_text_cache.get(filename)
    if text is None:
        try:
            with open(os.path.join(_ASSETS_DIR, filename), encoding="utf-8") as f:
                text = f.read()
        except OSError:  # pragma: no cover - 에셋 누락 대비
            text = ""
        _svg_text_cache[filename] = text
    return text


def _svg_renderer(filename, color):
    """currentColor 를 주어진 색으로 치환한 QSvgRenderer(캐시). 실패 시 None."""
    if not _HAS_SVG:
        return None
    color_hex = color.name()
    key = (filename, color_hex)
    renderer = _svg_renderer_cache.get(key)
    if renderer is None:
        text = _svg_text(filename)
        if not text:
            return None
        data = QByteArray(text.replace("currentColor", color_hex).encode("utf-8"))
        renderer = QSvgRenderer(data)
        _svg_renderer_cache[key] = renderer
    return renderer if renderer.isValid() else None


class CollapsibleGroupBox(QGroupBox):
    """접기/펴기가 가능한 QGroupBox.

    사용 예::

        box = CollapsibleGroupBox("옵션")
        layout = QVBoxLayout(box)
        layout.addWidget(QCheckBox("자동 저장"))
        box.setCollapsed(True)          # 접어 두고 시작

    QGroupBox 와 동일하게 동작하며, 아래 멤버가 추가된다.

    프로퍼티/메서드:
        - setCollapsed(bool) / isCollapsed() / collapsed (Qt 프로퍼티)
        - collapse() / expand() / toggleCollapsed()
        - setCollapsible(bool) / isCollapsible()  (False 면 접기 기능 자체를 끔)
        - setAnimated(bool) / isAnimated()
        - setAnimationDuration(int) / animationDuration()
        - setArrowColor(color)                    (화살표 색 지정, None=글자색)
        - setArrowStyle(style) / arrowStyle() / arrowStyles()  (셰브론·삼각형·±·SVG 3종)
        - setArrowSize(px) / arrowSize()          (None=폰트 자동, 환경변수 COLLAPSIBLE_ARROW_SIZE)
        - setTitle(text)                          (일반 텍스트 또는 HTML 리치텍스트)
        - setSummaryEnabled(bool) / isSummaryEnabled()  (접었을 때 요약 표시 on/off)
        - setSummary(text) / summary()            (접었을 때 보일 요약, HTML 가능)
        - setSummaryPosition(pos) / summaryPosition()   (SummaryBeside | SummaryInside)
        - summaryLabel()                          (요약 QLabel 직접 커스터마이즈)

    시그널:
        - collapsedChanged(bool): 접힘 상태가 바뀔 때 발생(True=접힘).
    """

    collapsedChanged = Signal(bool)

    # 요약 위치 옵션
    SummaryBeside = "beside"  # 제목 오른쪽편에
    SummaryInside = "inside"  # 접었을 때 박스 안쪽(제목 아래 줄)에

    # 접기/펴기 아이콘 스타일 — 직접 그리는 기본 3종
    ArrowChevron = "chevron"        # ˅ / › 셰브론 (기본, 회전 애니메이션)
    ArrowTriangle = "triangle"      # ▼ / ▶ 채워진 삼각형 (회전 애니메이션)
    ArrowPlusMinus = "plusminus"    # − / + 플러스·마이너스 (세로선 모핑)
    # 번들 SVG 아이콘 (회전 애니메이션, 글자색을 따라감)
    ArrowSvgDoubleChevron = "svg-double-chevron"  # 더블 셰브론 »
    ArrowSvgArrow = "svg-arrow"                    # 막대 화살표
    ArrowSvgCircle = "svg-circle"                  # 원 안 셰브론
    ArrowSvgCaret = "svg-caret"                    # 채워진 둥근 caret
    ArrowSvgChevronThick = "svg-chevron-thick"     # 굵은 둥근 셰브론
    ArrowSvgAngle = "svg-angle"                     # 넓은 각 셰브론

    # SVG 스타일 → 에셋 파일명
    _SVG_FILES = {
        ArrowSvgDoubleChevron: "double_chevron.svg",
        ArrowSvgArrow: "arrow.svg",
        ArrowSvgCircle: "circle_chevron.svg",
        ArrowSvgCaret: "caret.svg",
        ArrowSvgChevronThick: "chevron_thick.svg",
        ArrowSvgAngle: "angle.svg",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 생성자에 전달된 타이틀(C++ 경로로 설정되어 우리 setTitle 을 거치지 않음)을 회수한다.
        self._title = super().title()
        # 제목이 HTML 이면 QTextDocument 로 직접 그린다(_title_doc 캐시).
        self._is_rich = bool(self._title) and _might_be_rich(self._title)
        self._title_doc = None

        self._collapsed = False
        self._collapsible = True
        self._animated = True
        self._duration = 180  # ms

        # 화살표 상태: 0.0=접힘 ~ 1.0=펼침. 회전/모핑 애니메이션에 쓰인다.
        self._arrow_progress = 1.0
        self._arrow_color = None  # None 이면 팔레트(WindowText) 색을 따른다.
        self._arrow_style = self.ArrowChevron
        # None 이면 폰트 크기에 맞춰 자동. 환경변수 COLLAPSIBLE_ARROW_SIZE 로 기본값 지정 가능.
        self._arrow_size_override = _env_arrow_size()

        self._anim = None
        self._arrow_anim = None
        self._saved_min = self.minimumHeight()
        self._hidden_children = []

        # 제목 끝 글자가 라벨 영역에 빠듯하게 걸려 잘리지 않도록 두는 우측 여백(px).
        self._title_right_pad = 6
        self._applying_title = False  # _apply_display_title 재귀 가드
        self._hover_cursor = False    # 헤더 위에서 손가락 커서를 띄웠는지 여부

        # 요약 배치 옵션
        self._summary_position = self.SummaryBeside

        # 접었을 때 헤더에 보여줄 요약 라벨(기본 비활성). 마우스 이벤트는 통과시켜
        # 헤더 클릭 토글을 유지하고, 기본색은 보조정보처럼 살짝 흐리게 둔다.
        self._summary_enabled = False
        self._summary_label = QLabel(self)
        self._summary_label.setObjectName("collapsibleSummary")
        self._summary_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._summary_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        _spal = self._summary_label.palette()
        _scol = _spal.color(QPalette.WindowText)
        _scol.setAlpha(150)
        _spal.setColor(QPalette.WindowText, _scol)
        self._summary_label.setPalette(_spal)
        self._summary_label.hide()

        # 버튼을 누르지 않아도 헤더 위 hover 를 감지하려면 마우스 트래킹이 필요하다.
        self.setMouseTracking(True)
        self._refresh_title()

    # ------------------------------------------------------------------
    # 타이틀: 화살표 자리를 비워 두되 title()/setTitle() API 는 깔끔하게 유지
    # ------------------------------------------------------------------
    def setTitle(self, text):
        """타이틀을 설정한다(QGroupBox.setTitle 오버라이드).

        HTML(예: ``"<b>설정</b> <font color='#e67e22'>●</font>"``)을 주면 리치텍스트로
        렌더링한다. 일반 문자열이면 기존처럼 네이티브 렌더링/말줄임을 그대로 쓴다.
        """
        self._title = text or ""
        self._is_rich = bool(self._title) and _might_be_rich(self._title)
        self._title_doc = None  # 문서 캐시 무효화
        self._refresh_title()

    def title(self):
        """사용자가 설정한 타이틀 원본을 반환한다(HTML 이면 HTML 그대로)."""
        return self._title

    def _title_document(self):
        """리치텍스트 제목을 그릴 QTextDocument(캐시)."""
        if self._title_doc is None:
            doc = QTextDocument()
            doc.setDocumentMargin(0)
            doc.setDefaultFont(self.font())
            doc.setHtml(self._title)
            self._title_doc = doc
        return self._title_doc

    def _refresh_title(self):
        self._apply_display_title()

    def _apply_display_title(self):
        """표시용 제목을 갱신한다.

        - 화살표는 paintEvent 가 직접 그리므로, 텍스트 앞에 공백 들여쓰기를 넣어 자리만 비운다.
        - 현재 폭에서 제목이 라벨 영역을 넘으면 하드 클립 대신 말줄임(…)으로 줄인다.
          (전체 폭은 sizeHint/minimumSizeHint 가 별도로 보장하므로 줄어듦 피드백은 없다.)
        """
        if self._applying_title:
            return
        self._applying_title = True
        try:
            indent = self._title_indent()
            if self._is_rich:
                # 리치텍스트는 paintEvent 가 직접 그린다. 네이티브 제목은 상단 여백과
                # 라벨 위치를 잡기 위한 자리(들여쓰기 공백)만 둔다.
                if QGroupBox.title(self) != indent:
                    super().setTitle(indent)
                return

            fm = self.fontMetrics()
            # 라벨 시작 x 를 알기 위해 일단 전체 제목으로 세팅해 측정한다.
            full = indent + self._title
            if QGroupBox.title(self) != full:
                super().setTitle(full)

            w = self.width()
            if w <= 1 or not self._title:
                return  # 아직 크기 미정이거나 빈 제목이면 전체 표시

            label_x = self._subrect(QStyle.SC_GroupBoxLabel).left()
            indent_px = self._text_advance(indent)
            avail = int(w - label_x - indent_px - self._title_right_pad)
            elided = fm.elidedText(self._title, Qt.ElideRight, max(0, avail))
            disp = indent + elided
            if QGroupBox.title(self) != disp:
                super().setTitle(disp)
        finally:
            self._applying_title = False

    def _text_advance(self, text):
        fm = self.fontMetrics()
        fn = getattr(fm, "horizontalAdvance", None)
        return float(fn(text)) if fn is not None else float(fm.width(text))

    def _title_indent(self):
        if not self._collapsible:
            return ""
        need = self._arrow_size() + 8  # 화살표 폭 + 좌우 여백(px)
        space_w = max(1.0, self._text_advance(" "))
        return " " * (int(need / space_w) + 1)

    def setArrowColor(self, color):
        """화살표 색을 지정한다(None 이면 위젯 글자색을 따른다).

        QColor 또는 색 문자열("red", "#3498db" 등)을 받는다.
        """
        self._arrow_color = None if color is None else QColor(color)
        self.update()

    @classmethod
    def arrowStyles(cls):
        """선택 가능한 아이콘 스타일 목록(직접 그리는 3종 + 번들 SVG)."""
        return (
            cls.ArrowChevron, cls.ArrowTriangle, cls.ArrowPlusMinus,
        ) + tuple(cls._SVG_FILES.keys())

    def setArrowStyle(self, style):
        """접기/펴기 아이콘 모양을 고른다(arrowStyles() 중 하나).

        직접 그리는 ArrowChevron(기본)/ArrowTriangle/ArrowPlusMinus 와,
        번들 SVG 인 ArrowSvgDoubleChevron/ArrowSvgArrow/ArrowSvgCircle 이 있다.
        """
        if style not in self.arrowStyles():
            raise ValueError("unknown arrow style: %r" % (style,))
        if style == self._arrow_style:
            return
        self._arrow_style = style
        self.update()

    def arrowStyle(self):
        return self._arrow_style

    def setArrowSize(self, size):
        """접기/펴기 아이콘 크기(px)를 고정한다. None 이면 폰트 크기에 맞춰 자동 조절한다.

        전역 기본값은 환경변수 ``COLLAPSIBLE_ARROW_SIZE`` 로도 지정할 수 있다.
        """
        self._arrow_size_override = None if size is None else max(1, int(size))
        self._refresh_title()  # 화살표 자리(들여쓰기) 폭도 크기에 맞춰 갱신
        self._refresh_collapsed_height()  # 접힌 상태면 헤더 높이도 다시 고정
        self.updateGeometry()
        self.update()

    def arrowSize(self):
        """현재 적용 중인 화살표 크기(px). 자동 모드면 폰트 기준으로 계산된 값."""
        return self._arrow_size()

    # ------------------------------------------------------------------
    # 접힘 상태 API
    # ------------------------------------------------------------------
    def isCollapsed(self):
        return self._collapsed

    def setCollapsed(self, collapsed):
        """접힘 상태를 설정한다(True=접기). collapsible 이 False 면 무시된다."""
        collapsed = bool(collapsed)
        if collapsed == self._collapsed:
            return
        if collapsed and not self._collapsible:
            return

        self._collapsed = collapsed
        self._animate_arrow(0.0 if collapsed else 1.0)
        if collapsed:
            self._do_collapse()
        else:
            self._do_expand()
        self.collapsedChanged.emit(collapsed)

    def collapse(self):
        """접는다(setCollapsed(True) 의 단축)."""
        self.setCollapsed(True)

    def expand(self):
        """편다(setCollapsed(False) 의 단축)."""
        self.setCollapsed(False)

    def toggleCollapsed(self):
        """현재 상태를 반전한다."""
        self.setCollapsed(not self._collapsed)

    def isCollapsible(self):
        return self._collapsible

    def setCollapsible(self, collapsible):
        """접기 기능 자체의 사용 여부. False 면 항상 펼친 상태로 고정된다."""
        collapsible = bool(collapsible)
        if collapsible == self._collapsible:
            return
        self._collapsible = collapsible
        if not collapsible and self._collapsed:
            self.setCollapsed(False)
        if not collapsible:
            self._clear_hover_cursor()  # 손가락 커서 원복
        self._refresh_title()  # 화살표 자리(들여쓰기) 갱신
        self.update()

    def isAnimated(self):
        return self._animated

    def setAnimated(self, animated):
        """접기/펴기 애니메이션 사용 여부."""
        self._animated = bool(animated)

    def animationDuration(self):
        return self._duration

    def setAnimationDuration(self, ms):
        """애니메이션 길이(ms)."""
        self._duration = max(0, int(ms))

    # ------------------------------------------------------------------
    # 요약(접었을 때 헤더에 보이는 QLabel) API
    # ------------------------------------------------------------------
    def setSummaryEnabled(self, enabled):
        """접었을 때 요약을 보여주는 기능을 켜고 끈다(기본 꺼짐)."""
        self._summary_enabled = bool(enabled)
        self._refresh_collapsed_height()
        self._update_summary_label()

    def isSummaryEnabled(self):
        return self._summary_enabled

    def setSummary(self, text):
        """접었을 때 헤더에 표시할 요약 텍스트를 설정한다(HTML 도 가능)."""
        self._summary_label.setText(text or "")
        self._refresh_collapsed_height()
        self._update_summary_label()

    def summary(self):
        return self._summary_label.text()

    def summaryLabel(self):
        """요약 QLabel 자체를 돌려준다(색·폰트·스타일시트 등 커스터마이즈용)."""
        return self._summary_label

    def setSummaryPosition(self, position):
        """요약 위치: SummaryBeside(제목 오른쪽) 또는 SummaryInside(박스 안쪽)."""
        if position not in (self.SummaryBeside, self.SummaryInside):
            raise ValueError("position must be SummaryBeside or SummaryInside")
        if position == self._summary_position:
            return
        self._summary_position = position
        self._refresh_collapsed_height()
        self._update_summary_label()

    def summaryPosition(self):
        return self._summary_position

    def _refresh_collapsed_height(self):
        """접힌 상태에서 요약 옵션이 바뀌어 헤더 높이가 달라졌을 때 다시 고정한다.

        (SummaryInside 는 접힌 높이에 요약 줄을 더하므로, 요약을 켜거나 텍스트를
        넣고 빼면 접힌 박스 높이도 따라 바뀌어야 한다.)
        """
        if self._collapsed:
            self._stop_anim()
            self._set_box_height(self._header_height())

    def _title_right_edge(self):
        """헤더에서 제목 텍스트가 끝나는 x 좌표(요약을 그 옆에 붙이기 위함)."""
        if self._is_rich:
            x = self._title_left() + self._text_advance(self._title_indent())
            return x + self._title_document().idealWidth()
        return float(self._subrect(QStyle.SC_GroupBoxLabel).right())

    def _update_summary_label(self):
        """요약 라벨의 표시 여부·위치를 현재 상태/옵션에 맞춰 갱신한다."""
        lbl = self._summary_label
        if not (self._collapsed and self._summary_enabled and lbl.text()):
            lbl.hide()
            return

        if self._summary_position == self.SummaryInside:
            # 접힌 박스 안쪽(제목 줄 아래)에 한 줄로 배치
            m = self.contentsMargins()
            x = m.left() + 6
            width = self.width() - x - m.right() - 6
            y = self._title_band_height()
            height = self._summary_line_height()
        else:
            # 제목 오른쪽편에 배치
            x = int(self._title_right_edge() + 10)
            width = self.width() - x - 8
            y = 0
            height = self._title_band_height()

        if width < 16:
            lbl.hide()  # 표시할 공간이 없으면 숨긴다
            return
        lbl.setGeometry(int(x), int(y), int(width), int(height))
        lbl.show()
        lbl.raise_()

    # ------------------------------------------------------------------
    # 실제 접기/펴기 구현
    # ------------------------------------------------------------------
    def _content_children(self):
        # QGroupBox 는 내부 위젯 자식이 없으므로 사용자 콘텐츠만 추린다.
        # (요약 라벨은 헤더 장식이므로 접기/펴기 대상에서 제외한다.)
        return [
            c for c in self.children()
            if isinstance(c, QWidget) and c is not self._summary_label
        ]

    def _do_collapse(self):
        header = self._header_height()
        start = self.height()
        self._saved_min = self.minimumHeight()
        # 펼친 상태에서 명시적으로 보였던 자식만 기억해 둔다(나중에 그대로 복원).
        self._hidden_children = [w for w in self._content_children() if not w.isHidden()]

        self._stop_anim()
        if self._animated and self.isVisible() and start > header:
            self._animate(start, header, self._after_collapse)
        else:
            self._set_box_height(header)
            self._after_collapse()

    def _after_collapse(self):
        for w in self._hidden_children:
            w.hide()
        # 헤더 높이에 고정(접힌 동안 크기 유지).
        self._set_box_height(self._header_height())
        self._update_summary_label()  # 접힘 완료 → 요약 표시

    def _do_expand(self):
        self._update_summary_label()  # 펴기 시작 → 요약 즉시 숨김
        for w in self._hidden_children:
            w.show()
        self._hidden_children = []

        self._stop_anim()
        header = self.height()
        # 자식을 다시 보인 뒤의 원래 높이를 추정한다.
        self.updateGeometry()
        target = max(self.sizeHint().height(), header)

        if self._animated and self.isVisible() and target > header:
            self._set_box_height(header)
            self._animate(header, target, self._after_expand)
        else:
            self._after_expand()

    def _after_expand(self):
        # 높이 제약을 풀어 레이아웃이 자연스럽게 크기를 정하도록 한다.
        self.setMinimumHeight(self._saved_min)
        self.setMaximumHeight(_QWIDGETSIZE_MAX)

    # ------------------------------------------------------------------
    # 애니메이션 (min/max 높이를 동시에 고정하는 boxHeight 프로퍼티를 구동)
    # ------------------------------------------------------------------
    def _get_box_height(self):
        return self.maximumHeight()

    def _set_box_height(self, h):
        h = int(h)
        # min 과 max 를 같이 고정해 레이아웃 최소높이(자식 무관)를 강제로 무시한다.
        self.setMinimumHeight(h)
        self.setMaximumHeight(h)

    boxHeight = Property(int, _get_box_height, _set_box_height)

    def _start_animation(self, attr, prop, start, end, on_finish=None):
        """`attr` 슬롯의 이전 애니메이션을 정리하고 새 애니메이션을 시작한다.

        QPropertyAnimation 은 parent=self 로 만들어지므로, 정리하지 않으면 토글할
        때마다 self 의 자식으로 쌓여 메모리가 샌다. 중단·종료 양쪽에서 deleteLater 로 수거한다.
        """
        old = getattr(self, attr)
        if old is not None:
            old.stop()
            old.deleteLater()
        anim = QPropertyAnimation(self, prop, self)
        anim.setDuration(self._duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.InOutCubic)

        def _done():
            if on_finish is not None:
                on_finish()
            if getattr(self, attr) is anim:
                setattr(self, attr, None)
            anim.deleteLater()

        anim.finished.connect(_done)
        setattr(self, attr, anim)
        anim.start()

    def _animate(self, start, end, on_finish):
        self._start_animation("_anim", b"boxHeight", int(start), int(end), on_finish)

    def _stop_anim(self):
        if self._anim is not None:
            self._anim.stop()
            self._anim.deleteLater()
            self._anim = None

    # ------------------------------------------------------------------
    # 화살표 회전 애니메이션 (arrowProgress: 0=접힘 › ~ 1=펼침 ˅)
    # ------------------------------------------------------------------
    def _get_arrow_progress(self):
        return self._arrow_progress

    def _set_arrow_progress(self, v):
        self._arrow_progress = float(v)
        self.update()  # 화살표만 다시 그린다.

    arrowProgress = Property(float, _get_arrow_progress, _set_arrow_progress)

    def _stop_arrow_anim(self):
        if self._arrow_anim is not None:
            self._arrow_anim.stop()
            self._arrow_anim.deleteLater()
            self._arrow_anim = None

    def _animate_arrow(self, target):
        if not self._animated or not self.isVisible():
            self._stop_arrow_anim()
            self._set_arrow_progress(target)
            return
        self._start_animation(
            "_arrow_anim", b"arrowProgress", float(self._arrow_progress), float(target)
        )

    # ------------------------------------------------------------------
    # 헤더(타이틀 줄) 영역 계산 / 클릭 판정
    # ------------------------------------------------------------------
    def _style_option(self):
        opt = QStyleOptionGroupBox()
        self.initStyleOption(opt)
        return opt

    def _subrect(self, sub_control):
        opt = self._style_option()
        return self.style().subControlRect(QStyle.CC_GroupBox, opt, sub_control, self)

    def _frame_top(self):
        """그룹박스 프레임 상단 선 두께(px)."""
        fw = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth, self._style_option(), self)
        return max(2, fw)

    def _summary_line_height(self):
        return self._summary_label.sizeHint().height() + 4

    def _summary_inside_active(self):
        return (self._summary_position == self.SummaryInside
                and self._summary_enabled and bool(self._summary_label.text()))

    def _title_band_height(self):
        """제목/화살표가 놓이는 헤더 상단 줄(제목 줄)의 높이."""
        label = self._subrect(QStyle.SC_GroupBoxLabel)
        checkbox = self._subrect(QStyle.SC_GroupBoxCheckBox)
        bottom = max(label.bottom(), checkbox.bottom(), 0)
        h = max(bottom + max(4, self._frame_top()), self.fontMetrics().height() + 6)
        if self._collapsible:
            # 폰트보다 큰 아이콘을 줘도 헤더 줄 안에 담겨 잘리지 않도록 한다.
            h = max(h, self._arrow_size() + 4)
        return h

    def _header_height(self):
        """접었을 때 남길 총 높이(제목 줄 + 필요 시 안쪽 요약 줄)."""
        h = self._title_band_height()
        if self._summary_inside_active():
            h += self._summary_line_height()
        return h

    def _title_left(self):
        """제목/화살표가 시작하는 왼쪽 x(들여쓰기 자리의 시작)."""
        return self._subrect(QStyle.SC_GroupBoxLabel).left()

    def _title_band(self):
        """제목/화살표가 놓이는 헤더 상단 줄(제목 줄)의 사각형."""
        return self._subrect(QStyle.SC_GroupBoxLabel)

    def _header_hit(self, pos):
        """주어진 위치가 제목 줄(접기 토글) 영역 안인지 판정한다.

        라벨(글자) 부분뿐 아니라 제목 줄 높이 범위의 가로 전체를 헤더로 본다.
        """
        return 0 <= pos.y() <= self._header_height()

    def _checkbox_hit(self, pos):
        """체크 가능 그룹박스의 체크박스 인디케이터 위인지 판정한다."""
        if not self.isCheckable():
            return False
        return self._subrect(QStyle.SC_GroupBoxCheckBox).contains(pos)

    # ------------------------------------------------------------------
    # 화살표(셰브론) 그리기
    # ------------------------------------------------------------------
    def _arrow_size(self):
        """화살표 한 변의 픽셀 크기(설정값 우선, 없으면 폰트에 맞춰 자동)."""
        if self._arrow_size_override is not None:
            return self._arrow_size_override
        return max(9, int(self.fontMetrics().height() * 0.62))

    def _arrow_rect(self):
        """화살표를 그릴 정사각형 영역(제목 줄 왼쪽 들여쓰기 자리)."""
        size = self._arrow_size()
        cx = self._title_left() + size / 2.0 + 2.0
        cy = self._title_band_height() / 2.0  # 헤더 줄 세로 중앙(아이콘 크기 반영)
        return QRectF(cx - size / 2.0, cy - size / 2.0, size, size)

    def _title_text_color(self):
        # 비활성화면 제목/화살표가 함께 흐려지도록 color group 을 맞춘다.
        group = QPalette.Normal if self.isEnabled() else QPalette.Disabled
        return self.palette().color(group, QPalette.WindowText)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._collapsible and not self._is_rich:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self._is_rich:
            self._draw_rich_title(painter, self._title_band())
        if self._collapsible:
            self._draw_arrow(painter)
        painter.end()

    def _draw_arrow(self, painter):
        rect = self._arrow_rect()
        size = rect.width()
        color = self._arrow_color if self._arrow_color is not None else self._title_text_color()
        style = self._arrow_style
        if style in self._SVG_FILES:
            if self._draw_svg(painter, rect, size, color, self._SVG_FILES[style]):
                return
            # SVG 로드 실패 시 셰브론으로 graceful fallback
        if style == self.ArrowPlusMinus:
            self._draw_plus_minus(painter, rect, size, color)
        elif style == self.ArrowTriangle:
            self._draw_triangle(painter, rect, size, color)
        else:
            self._draw_chevron(painter, rect, size, color)

    def _draw_svg(self, painter, rect, size, color, filename):
        """번들 SVG 아이콘을 회전시켜 그린다. 성공하면 True."""
        renderer = _svg_renderer(filename, color)
        if renderer is None:
            return False
        painter.save()
        painter.translate(rect.center())
        # 셰브론과 동일하게 0(접힘)=오른쪽 ~ 1(펼침)=아래로 회전.
        painter.rotate(-90.0 * (1.0 - self._arrow_progress))
        painter.translate(-size / 2.0, -size / 2.0)
        renderer.render(painter, QRectF(0.0, 0.0, size, size))
        painter.restore()
        return True

    def _stroke_pen(self, color, size):
        pen = QPen(color)
        pen.setWidthF(max(1.5, size * 0.16))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    def _draw_chevron(self, painter, rect, size, color):
        painter.save()
        painter.translate(rect.center())
        # progress 0(접힘)=오른쪽(›), 1(펼침)=아래(˅). ˅ 모양을 반시계로 0~90° 회전.
        painter.rotate(-90.0 * (1.0 - self._arrow_progress))
        painter.setPen(self._stroke_pen(color, size))
        w = size * 0.30
        d = size * 0.16
        painter.drawPolyline(QPolygonF([
            QPointF(-w, -d),
            QPointF(0.0, d),
            QPointF(w, -d),
        ]))
        painter.restore()

    def _draw_triangle(self, painter, rect, size, color):
        painter.save()
        painter.translate(rect.center())
        # progress 1(펼침)=▼, 0(접힘)=▶ — ▼ 모양을 반시계로 0~90° 회전.
        painter.rotate(-90.0 * (1.0 - self._arrow_progress))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        w = size * 0.32
        painter.drawPolygon(QPolygonF([
            QPointF(-w, -w * 0.55),
            QPointF(w, -w * 0.55),
            QPointF(0.0, w * 0.72),
        ]))
        painter.restore()

    def _draw_plus_minus(self, painter, rect, size, color):
        painter.save()
        painter.translate(rect.center())
        painter.setPen(self._stroke_pen(color, size))
        a = size * 0.32  # 선 반 길이
        painter.drawLine(QPointF(-a, 0.0), QPointF(a, 0.0))  # 가로선은 항상
        # 세로선은 접힘(progress 0, +)에서 가장 길고 펼침(1, −)에서 사라진다.
        v = a * (1.0 - self._arrow_progress)
        if v > 0.5:
            painter.drawLine(QPointF(0.0, -v), QPointF(0.0, v))
        painter.restore()

    def _draw_rich_title(self, painter, band):
        """HTML 제목을 QTextDocument 로 제목 줄(band) 위치에 직접 그린다."""
        doc = self._title_document()
        x = self._title_left() + self._text_advance(self._title_indent())
        doc_size = doc.size()
        y = band.center().y() - doc_size.height() / 2.0

        # 네이티브가 그린 자리(공백)·프레임 선 잔상을 지운 뒤 리치텍스트를 얹는다.
        bg = self.palette().color(QPalette.Window)
        painter.fillRect(
            QRectF(x, band.top(), doc_size.width() + 2.0, band.height()), bg
        )

        painter.save()
        painter.translate(x, y)
        painter.setPen(self._title_text_color())  # HTML 에서 색 미지정 부분의 기본색
        doc.drawContents(painter)
        painter.restore()

    # ------------------------------------------------------------------
    # 크기 힌트: 표시 제목이 말줄임되어도 "전체 제목 + 우측 여백" 폭을 보장한다.
    # (이 덕분에 레이아웃이 폭을 줄여 제목을 잘리게 만들지 않고, 끝 글자 잘림도 막는다.)
    # ------------------------------------------------------------------
    def _expand_hint_width(self, base):
        # 리치텍스트는 제목을 우리가 직접 그리므로 base(네이티브)가 제목 폭을 모른다.
        # 제목이 들어갈 폭을 직접 보장한다.
        if self._is_rich:
            x = self._title_left() + self._text_advance(self._title_indent())
            need = int(x + self._title_document().idealWidth() + self._title_right_pad)
            return QSize(max(base.width(), need), base.height())
        # base 는 현재(말줄임됐을 수도 있는) 표시 제목 기준이므로, 줄어든 폭을 되돌려 더해 준다.
        full = self._title_indent() + self._title
        shown = QGroupBox.title(self)
        extra = self._text_advance(full) - self._text_advance(shown)
        pad = int(max(0.0, extra)) + self._title_right_pad
        return QSize(base.width() + pad, base.height())

    def sizeHint(self):
        return self._expand_hint_width(super().sizeHint())

    def minimumSizeHint(self):
        return self._expand_hint_width(super().minimumSizeHint())

    # ------------------------------------------------------------------
    # 이벤트
    # ------------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 폭이 바뀐 경우에만 말줄임을 다시 계산한다. (접기/펴기 애니메이션은 높이만
        # 바꾸므로, 폭 불변 시 재계산을 건너뛰어 매 프레임 setTitle 왕복을 막는다.)
        if event.oldSize().width() != event.size().width():
            self._apply_display_title()
        self._update_summary_label()  # 접힌 상태면 요약 위치/폭 재배치

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_display_title()
        self._update_summary_label()

    def changeEvent(self, event):
        super().changeEvent(event)
        # super().__init__() 도중(폰트/스타일 적용 시)에도 불릴 수 있으므로,
        # 인스턴스 속성이 아직 준비되지 않았으면 건너뛴다.
        if not hasattr(self, "_applying_title"):
            return
        # 폰트/스타일이 바뀌면 들여쓰기 폭·화살표 크기·라벨 위치가 달라지므로 다시 계산한다.
        if event.type() in (QEvent.FontChange, QEvent.StyleChange):
            self._title_doc = None  # 폰트 바뀌면 리치텍스트 문서도 다시 만든다.
            self._refresh_title()
            self._refresh_collapsed_height()  # 헤더 높이 변화 → 접힌 박스 높이 재고정
            self._update_summary_label()
            self.update()
        elif event.type() == QEvent.EnabledChange:
            self.update()  # 화살표 색을 활성/비활성에 맞춰 다시 그린다.

    def mousePressEvent(self, event):
        if self._collapsible and event.button() == Qt.LeftButton:
            pos = _event_point(event)
            # 체크박스 인디케이터 클릭은 QGroupBox 의 체크 토글로 양보한다.
            if self._header_hit(pos) and not self._checkbox_hit(pos):
                self.toggleCollapsed()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 제목 줄 위에 마우스가 있으면 손가락 커서로, 벗어나면 기본 커서로 바꾼다.
        pos = _event_point(event)
        on_header = (
            self._collapsible
            and self._header_hit(pos)
            and not self._checkbox_hit(pos)
        )
        if on_header:
            self._set_hover_cursor()
        else:
            self._clear_hover_cursor()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._clear_hover_cursor()
        super().leaveEvent(event)

    def _set_hover_cursor(self):
        if not self._hover_cursor:
            self.setCursor(Qt.PointingHandCursor)
            self._hover_cursor = True

    def _clear_hover_cursor(self):
        if self._hover_cursor:
            self.unsetCursor()
            self._hover_cursor = False

    # Qt Designer / 스타일시트에서 쓸 수 있는 프로퍼티
    collapsed = Property(bool, isCollapsed, setCollapsed)
