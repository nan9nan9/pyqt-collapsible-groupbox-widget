"""pyqt-collapsible-groupbox-widget — 접을 수 있는 QGroupBox 위젯.

다른 프로그램에서는 한 줄로 가져다 쓴다::

    from collapsible_groupbox import CollapsibleGroupBox

`QGroupBox` 와 API 가 호환되며, 제목 클릭(또는 메서드 호출)으로 접기/펴기가 된다.
qtpy 추상화로 PyQt5 / PyQt6 / PySide2 / PySide6 모두에서 동작한다.
"""

from __future__ import annotations

from .collapsible_group_box import CollapsibleGroupBox

__all__ = ["CollapsibleGroupBox"]

__version__ = "0.1.0"
