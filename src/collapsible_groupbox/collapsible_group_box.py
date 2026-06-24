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

from qtpy.QtCore import (
    Qt, Signal, Property, QPropertyAnimation, QEasingCurve, QRectF, QPointF,
)
from qtpy.QtGui import QPainter, QPen, QPolygonF, QPalette
from qtpy.QtWidgets import (
    QGroupBox,
    QWidget,
    QStyle,
    QStyleOptionGroupBox,
)

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

    시그널:
        - collapsedChanged(bool): 접힘 상태가 바뀔 때 발생(True=접힘).
    """

    collapsedChanged = Signal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 생성자에 전달된 타이틀(C++ 경로로 설정되어 우리 setTitle 을 거치지 않음)을 회수한다.
        self._title = super().title()

        self._collapsed = False
        self._collapsible = True
        self._animated = True
        self._duration = 180  # ms

        # 셰브론 화살표 상태: 0.0=접힘(›) ~ 1.0=펼침(˅). 회전 애니메이션에 쓰인다.
        self._arrow_progress = 1.0
        self._arrow_color = None  # None 이면 팔레트(WindowText) 색을 따른다.

        self._anim = None
        self._arrow_anim = None
        self._saved_min = self.minimumHeight()
        self._hidden_children = []

        self.setCursor(Qt.PointingHandCursor)
        self._refresh_title()

    # ------------------------------------------------------------------
    # 타이틀: 화살표 자리를 비워 두되 title()/setTitle() API 는 깔끔하게 유지
    # ------------------------------------------------------------------
    def setTitle(self, text):
        """타이틀을 설정한다(QGroupBox.setTitle 오버라이드)."""
        self._title = text or ""
        self._refresh_title()

    def title(self):
        """사용자가 설정한 순수 타이틀을 반환한다(화살표 들여쓰기 제외)."""
        return self._title

    def _refresh_title(self):
        # 화살표는 paintEvent 가 직접 그린다. 텍스트 앞에 공백을 넣어 그릴 자리만 비운다.
        super().setTitle(self._title_indent() + self._title)

    def _title_indent(self):
        if not self._collapsible:
            return ""
        need = self._arrow_size() + 8  # 화살표 폭 + 좌우 여백(px)
        space_w = max(1.0, self._space_advance())
        return " " * (int(need / space_w) + 1)

    def _space_advance(self):
        # 공백 한 칸의 픽셀 폭(Qt6: horizontalAdvance, Qt5: width).
        fm = self.fontMetrics()
        fn = getattr(fm, "horizontalAdvance", None)
        return float(fn(" ")) if fn is not None else float(fm.width(" "))

    def setArrowColor(self, color):
        """화살표 색을 지정한다(None 이면 위젯 글자색을 따른다)."""
        self._arrow_color = color
        self.update()

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
        self.setCursor(Qt.PointingHandCursor if collapsible else Qt.ArrowCursor)
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
    # 실제 접기/펴기 구현
    # ------------------------------------------------------------------
    def _content_children(self):
        # QGroupBox 는 내부 위젯 자식이 없으므로 모든 QWidget 자식은 사용자 콘텐츠다.
        return [c for c in self.children() if isinstance(c, QWidget)]

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

    def _do_expand(self):
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

    def _animate(self, start, end, on_finish):
        anim = QPropertyAnimation(self, b"boxHeight", self)
        anim.setDuration(self._duration)
        anim.setStartValue(int(start))
        anim.setEndValue(int(end))
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        if on_finish is not None:
            anim.finished.connect(on_finish)
        self._anim = anim
        anim.start()

    def _stop_anim(self):
        if self._anim is not None:
            self._anim.stop()
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

    def _animate_arrow(self, target):
        if self._arrow_anim is not None:
            self._arrow_anim.stop()
            self._arrow_anim = None
        if not self._animated or not self.isVisible():
            self._set_arrow_progress(target)
            return
        anim = QPropertyAnimation(self, b"arrowProgress", self)
        anim.setDuration(self._duration)
        anim.setStartValue(float(self._arrow_progress))
        anim.setEndValue(float(target))
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._arrow_anim = anim
        anim.start()

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

    def _header_height(self):
        """접었을 때 남길 높이(타이틀 줄 높이)를 스타일에서 계산한다."""
        label = self._subrect(QStyle.SC_GroupBoxLabel)
        checkbox = self._subrect(QStyle.SC_GroupBoxCheckBox)
        bottom = max(label.bottom(), checkbox.bottom(), 0)
        frame = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth, self._style_option(), self)
        h = bottom + max(4, frame)
        return max(h, self.fontMetrics().height() + 6)

    def _header_hit(self, pos):
        """주어진 위치가 타이틀(접기 토글) 영역 안인지 판정한다."""
        return self._subrect(QStyle.SC_GroupBoxLabel).contains(pos)

    def _checkbox_hit(self, pos):
        """체크 가능 그룹박스의 체크박스 인디케이터 위인지 판정한다."""
        if not self.isCheckable():
            return False
        return self._subrect(QStyle.SC_GroupBoxCheckBox).contains(pos)

    # ------------------------------------------------------------------
    # 화살표(셰브론) 그리기
    # ------------------------------------------------------------------
    def _arrow_size(self):
        """화살표 한 변의 픽셀 크기."""
        return max(9, int(self.fontMetrics().height() * 0.62))

    def _arrow_rect(self):
        """화살표를 그릴 정사각형 영역(타이틀 라벨 왼쪽 들여쓰기 자리)."""
        label = self._subrect(QStyle.SC_GroupBoxLabel)
        size = self._arrow_size()
        cx = label.left() + size / 2.0 + 2.0
        cy = label.center().y() + 1.0
        return QRectF(cx - size / 2.0, cy - size / 2.0, size, size)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._collapsible:
            return

        rect = self._arrow_rect()
        size = rect.width()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.translate(rect.center())
        # progress 0(접힘)=오른쪽(›), 1(펼침)=아래(˅). ˅ 모양을 반시계로 0~90° 회전.
        painter.rotate(-90.0 * (1.0 - self._arrow_progress))

        color = self._arrow_color
        if color is None:
            color = self.palette().color(QPalette.WindowText)
        pen = QPen(color)
        pen.setWidthF(max(1.5, size * 0.16))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        # ˅ 모양 셰브론(중심 기준): 왼쪽 위 → 가운데 아래 → 오른쪽 위
        w = size * 0.30
        d = size * 0.16
        painter.drawPolyline(QPolygonF([
            QPointF(-w, -d),
            QPointF(0.0, d),
            QPointF(w, -d),
        ]))
        painter.end()

    # ------------------------------------------------------------------
    # 이벤트
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if self._collapsible and event.button() == Qt.LeftButton:
            pos = _event_point(event)
            # 체크박스 인디케이터 클릭은 QGroupBox 의 체크 토글로 양보한다.
            if self._header_hit(pos) and not self._checkbox_hit(pos):
                self.toggleCollapsed()
                event.accept()
                return
        super().mousePressEvent(event)

    # Qt Designer / 스타일시트에서 쓸 수 있는 프로퍼티
    collapsed = Property(bool, isCollapsed, setCollapsed)
