"""CollapsibleGroupBox 단위 테스트.

헤드리스 실행::

    QT_QPA_PLATFORM=offscreen python3 -m pytest -q
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy.QtCore import Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QApplication, QVBoxLayout, QLabel, QStyle

from collapsible_groupbox import CollapsibleGroupBox


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication(sys.argv)
    yield a


def _make_box(title="제목", n_children=3):
    box = CollapsibleGroupBox(title)
    lay = QVBoxLayout(box)
    children = [QLabel("줄 %d" % i) for i in range(n_children)]
    for c in children:
        lay.addWidget(c)
    box.setAnimated(False)  # 테스트는 즉시 반영되도록 애니메이션 끔
    return box, children


def test_is_qgroupbox_subclass(app):
    from qtpy.QtWidgets import QGroupBox
    box, _ = _make_box()
    assert isinstance(box, QGroupBox)


def test_title_roundtrip_without_arrow(app):
    # title() 은 화살표가 섞이지 않은 순수 제목을 반환해야 한다.
    box, _ = _make_box("내 제목")
    assert box.title() == "내 제목"
    box.setTitle("바뀐 제목")
    assert box.title() == "바뀐 제목"


def test_constructor_title_recovered(app):
    box = CollapsibleGroupBox("생성자 제목")
    assert box.title() == "생성자 제목"


def test_default_expanded(app):
    box, _ = _make_box()
    assert box.isCollapsed() is False


def test_collapse_hides_children(app):
    box, children = _make_box()
    box.show()
    box.setCollapsed(True)
    assert box.isCollapsed() is True
    for c in children:
        assert c.isHidden() is True


def test_expand_restores_children(app):
    box, children = _make_box()
    box.show()
    box.setCollapsed(True)
    box.setCollapsed(False)
    assert box.isCollapsed() is False
    for c in children:
        assert c.isHidden() is False


def test_toggle(app):
    box, _ = _make_box()
    box.show()
    assert box.isCollapsed() is False
    box.toggleCollapsed()
    assert box.isCollapsed() is True
    box.toggleCollapsed()
    assert box.isCollapsed() is False


def test_collapsed_changed_signal(app):
    box, _ = _make_box()
    box.show()
    seen = []
    box.collapsedChanged.connect(seen.append)
    box.setCollapsed(True)
    box.setCollapsed(True)  # 변화 없으면 재발생하지 않아야 한다
    box.setCollapsed(False)
    assert seen == [True, False]


def test_collapse_reduces_height(app):
    box, _ = _make_box(n_children=5)
    box.resize(200, 200)
    box.show()
    full = box.height()
    box.setCollapsed(True)
    assert box.height() < full


def test_not_collapsible_blocks_collapse(app):
    box, _ = _make_box()
    box.show()
    box.setCollapsible(False)
    box.setCollapsed(True)
    assert box.isCollapsed() is False


def test_set_collapsible_false_expands(app):
    box, _ = _make_box()
    box.show()
    box.setCollapsed(True)
    box.setCollapsible(False)
    assert box.isCollapsed() is False


def test_header_click_toggles(app):
    box, _ = _make_box()
    box.resize(200, 160)
    box.show()
    # 타이틀 라벨 영역 중앙을 클릭
    label_rect = box._subrect(QStyle.SC_GroupBoxLabel)
    pt = label_rect.center()
    press = QMouseEvent(QMouseEvent.MouseButtonPress, pt, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(box, press)
    assert box.isCollapsed() is True


def test_header_click_outside_label_toggles(app):
    # 라벨(글자) 바깥, 제목 줄 오른쪽 빈 영역을 클릭해도 토글되어야 한다.
    from qtpy.QtCore import QPoint
    box, _ = _make_box()
    box.resize(240, 160)
    box.show()
    hh = box._header_height()
    pt = QPoint(box.width() - 12, hh // 2)  # 제목 줄 우측 끝
    assert box._header_hit(pt) is True
    press = QMouseEvent(QMouseEvent.MouseButtonPress, pt, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(box, press)
    assert box.isCollapsed() is True


def test_content_click_does_not_toggle(app):
    # 콘텐츠 영역(헤더 줄 아래) 클릭은 토글하지 않아야 한다.
    from qtpy.QtCore import QPoint
    box, _ = _make_box()
    box.resize(240, 160)
    box.show()
    pt = QPoint(box.width() // 2, box._header_height() + 40)
    assert box._header_hit(pt) is False
    press = QMouseEvent(QMouseEvent.MouseButtonPress, pt, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(box, press)
    assert box.isCollapsed() is False


def test_hover_cursor_on_header_only(app):
    from qtpy.QtCore import QPoint
    box, _ = _make_box()
    box.resize(240, 160)
    box.show()
    hh = box._header_height()

    def move(x, y):
        ev = QMouseEvent(QMouseEvent.MouseMove, QPoint(x, y), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        QApplication.sendEvent(box, ev)

    move(box.width() - 12, hh // 2)  # 헤더 위
    assert box.cursor().shape() == Qt.PointingHandCursor
    move(box.width() // 2, hh + 40)  # 콘텐츠 위
    assert box.cursor().shape() == Qt.ArrowCursor


def test_arrow_progress_follows_state(app):
    # 화살표 회전 진행도: 펼침=1.0, 접힘=0.0 (애니메이션 끈 상태에서 즉시 반영).
    box, _ = _make_box("X")
    box.show()
    assert box._arrow_progress == 1.0
    box.setCollapsed(True)
    assert box._arrow_progress == 0.0
    box.setCollapsed(False)
    assert box._arrow_progress == 1.0


def test_title_has_arrow_indent(app):
    # 화살표를 그릴 자리를 비우기 위해 표시 제목 앞에 공백 들여쓰기가 들어간다.
    from qtpy.QtWidgets import QGroupBox
    box, _ = _make_box("제목")
    shown = QGroupBox.title(box)
    assert shown.endswith("제목") and shown != "제목"
    assert box.title() == "제목"  # 순수 제목은 그대로


def test_minimum_size_hint_fits_full_title(app):
    # 최소 너비 힌트는 (화살표 들여쓰기 + 전체 제목 + 우측 여백)을 모두 담아야 잘리지 않는다.
    long_title = "아주 길고 긴 그룹 제목입니다 끝까지 보여야 함 ABCg"
    box = CollapsibleGroupBox(long_title)
    QVBoxLayout(box).addWidget(QLabel("x"))
    box.setAnimated(False)
    box.show()
    fm = box.fontMetrics()
    adv = getattr(fm, "horizontalAdvance", fm.width)
    full_w = adv(box._title_indent() + long_title)
    assert box.minimumSizeHint().width() >= full_w


def test_long_title_elides_when_narrow(app):
    from qtpy.QtWidgets import QGroupBox
    long_title = "아주 길고 긴 그룹 제목입니다 끝까지 보여야 함 ABCg"
    box = CollapsibleGroupBox(long_title)
    QVBoxLayout(box).addWidget(QLabel("x"))
    box.setAnimated(False)
    box.show()
    box.resize(140, 90)
    app.processEvents()
    shown = QGroupBox.title(box)
    assert "…" in shown          # 좁으면 말줄임
    assert box.title() == long_title  # 순수 제목은 보존


def test_resize_does_not_corrupt_pure_title(app):
    long_title = "끝 글자 확인용 제목 ABCg"
    box = CollapsibleGroupBox(long_title)
    QVBoxLayout(box).addWidget(QLabel("x"))
    box.setAnimated(False)
    box.show()
    for w in (300, 200, 130, 250, 400):
        box.resize(w, 90)
        app.processEvents()
        assert box.title() == long_title  # 폭을 아무리 바꿔도 순수 제목은 불변


def test_animations_do_not_leak(app):
    # 토글을 반복해도 QPropertyAnimation 객체가 위젯에 무한히 쌓이지 않아야 한다.
    from qtpy.QtCore import QPropertyAnimation, QEventLoop, QTimer
    box, _ = _make_box()
    box.setAnimated(True)
    box.resize(200, 150)
    box.show()
    for _ in range(15):
        box.toggleCollapsed()
        app.processEvents()
    # 진행 중인 애니메이션이 끝나고 deleteLater 가 처리되도록 잠시 이벤트 루프를 돌린다.
    loop = QEventLoop()
    QTimer.singleShot(500, loop.quit)
    loop.exec_()
    assert len(box.findChildren(QPropertyAnimation)) == 0


def test_arrow_color_accepts_string_and_none(app):
    from qtpy.QtGui import QColor
    box, _ = _make_box()
    box.setArrowColor("red")
    assert isinstance(box._arrow_color, QColor)
    assert box._arrow_color.name() == "#ff0000"
    box.setArrowColor(None)
    assert box._arrow_color is None


def test_font_change_updates_indent(app):
    from qtpy.QtGui import QFont
    box, _ = _make_box("제목")
    box.show()
    indent_small = box._title_indent()
    box.setFont(QFont(box.font().family(), 28))
    app.processEvents()
    # 폰트가 커지면 화살표 자리 들여쓰기의 픽셀 폭도 갱신되어야 한다(공백 폭 기준 재계산).
    fm = box.fontMetrics()
    adv = getattr(fm, "horizontalAdvance", fm.width)
    assert adv(box._title_indent()) >= box._arrow_size()
    assert indent_small is not None  # 단순 존재 확인


def test_html_title_detected_as_rich(app):
    box, _ = _make_box()
    box.setTitle("<b>설정</b> <font color='#e67e22'>●</font> 고급")
    assert box._is_rich is True
    assert box.title() == "<b>설정</b> <font color='#e67e22'>●</font> 고급"  # 원본 보존


def test_plain_title_not_rich(app):
    box, _ = _make_box()
    box.setTitle("그냥 제목")
    assert box._is_rich is False


def test_html_title_paints_without_error(app):
    box, _ = _make_box()
    box.setTitle("<b>굵게</b> <i>기울임</i> <font color='red'>빨강</font>")
    box.resize(260, 150)
    box.show()
    app.processEvents()
    img = box.grab()  # paintEvent(_draw_rich_title)가 예외 없이 실행되어야 한다
    assert not img.isNull()


def test_html_minimum_width_fits_document(app):
    box, _ = _make_box()
    box.setTitle("<b>아주 길고 긴 리치텍스트 제목입니다 ABCDEFG</b>")
    box.show()
    app.processEvents()
    doc_w = box._title_document().idealWidth()
    assert box.minimumSizeHint().width() >= doc_w


def test_switch_html_to_plain_restores_path(app):
    from qtpy.QtWidgets import QGroupBox
    box, _ = _make_box()
    box.setTitle("<b>HTML</b>")
    assert box._is_rich is True
    box.setTitle("plain 으로 변경")
    assert box._is_rich is False
    # plain 경로로 돌아오면 네이티브 제목에 (들여쓰기+제목)이 다시 들어간다.
    assert QGroupBox.title(box).endswith("plain 으로 변경")


def test_summary_shows_only_when_collapsed(app):
    box, _ = _make_box()
    box.setSummaryEnabled(True)
    box.setSummary("요약 텍스트")
    box.resize(280, 160)
    box.show()
    app.processEvents()
    assert box.summaryLabel().isVisible() is False  # 펼침 상태엔 숨김
    box.setCollapsed(True)
    app.processEvents()
    assert box.summaryLabel().isVisible() is True    # 접으면 표시
    box.setCollapsed(False)
    app.processEvents()
    assert box.summaryLabel().isVisible() is False    # 다시 펴면 숨김


def test_summary_disabled_stays_hidden(app):
    box, _ = _make_box()
    box.setSummary("요약")
    box.resize(280, 160)
    box.show()
    box.setCollapsed(True)
    app.processEvents()
    # 기본은 비활성이므로 접어도 안 보인다.
    assert box.isSummaryEnabled() is False
    assert box.summaryLabel().isVisible() is False
    # 활성화하면 보이고, 다시 끄면 숨는다.
    box.setSummaryEnabled(True)
    app.processEvents()
    assert box.summaryLabel().isVisible() is True
    box.setSummaryEnabled(False)
    app.processEvents()
    assert box.summaryLabel().isVisible() is False


def test_empty_summary_not_shown(app):
    box, _ = _make_box()
    box.setSummaryEnabled(True)
    box.resize(280, 160)
    box.show()
    box.setCollapsed(True)
    app.processEvents()
    # 요약 텍스트가 비어 있으면 표시하지 않는다.
    assert box.summaryLabel().isVisible() is False
    assert box.summary() == ""


def test_summary_label_excluded_from_collapse(app):
    # 요약 라벨은 콘텐츠가 아니므로 접기/펴기 시 hide/show 대상에서 제외된다.
    box, _ = _make_box()
    box.setSummaryEnabled(True)
    box.setSummary("s")
    box.show()
    box.setCollapsed(True)
    box.setCollapsed(False)
    app.processEvents()
    assert box._summary_label not in box._content_children()


def test_summary_position_default(app):
    box, _ = _make_box()
    assert box.summaryPosition() == CollapsibleGroupBox.SummaryBeside


def test_invalid_summary_position_raises(app):
    box, _ = _make_box()
    with pytest.raises(ValueError):
        box.setSummaryPosition("nope")


def test_summary_inside_is_taller_when_collapsed(app):
    def collapsed_height(summary_pos):
        b = CollapsibleGroupBox("제목")
        QVBoxLayout(b).addWidget(QLabel("x"))
        b.setAnimated(False)
        b.setSummaryEnabled(True)
        b.setSummary("요약")
        b.setSummaryPosition(summary_pos)
        b.resize(240, 160)
        b.show()
        b.setCollapsed(True)
        app.processEvents()
        return b.height()

    beside = collapsed_height(CollapsibleGroupBox.SummaryBeside)
    inside = collapsed_height(CollapsibleGroupBox.SummaryInside)
    assert inside > beside  # Inside 는 제목 줄 + 요약 줄이라 더 높다


def test_summary_position_combos_paint(app):
    for sp in (CollapsibleGroupBox.SummaryBeside, CollapsibleGroupBox.SummaryInside):
        box = CollapsibleGroupBox("제목")
        QVBoxLayout(box).addWidget(QLabel("내용"))
        box.setAnimated(False)
        box.setSummaryEnabled(True)
        box.setSummary("요약")
        box.setSummaryPosition(sp)
        box.resize(260, 150)
        box.show()
        box.setCollapsed(True)
        app.processEvents()
        assert not box.grab().isNull()


def test_animation_props(app):
    box, _ = _make_box()
    box.setAnimated(True)
    assert box.isAnimated() is True
    box.setAnimationDuration(300)
    assert box.animationDuration() == 300


def test_checkable_coexists(app):
    # 체크 가능 그룹박스로 써도 깨지지 않아야 한다(접기 API 는 독립적으로 동작).
    box, _ = _make_box()
    box.setCheckable(True)
    box.show()
    box.setCollapsed(True)
    assert box.isCollapsed() is True
    assert box.isCheckable() is True
