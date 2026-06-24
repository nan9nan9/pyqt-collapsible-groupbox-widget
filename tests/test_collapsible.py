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
