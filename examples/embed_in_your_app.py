"""기존 앱에 임베드하는 최소 예제.

핵심: 기존에 `QGroupBox` 를 쓰던 코드를 `CollapsibleGroupBox` 로 바꾸기만 하면
접기/펴기 기능이 추가된다. 나머지 사용법(레이아웃, setTitle, setCheckable 등)은
QGroupBox 와 완전히 동일하다.

실행::

    python3 examples/embed_in_your_app.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from qtpy.QtWidgets import QApplication, QWidget, QFormLayout, QLineEdit, QVBoxLayout

from collapsible_groupbox import CollapsibleGroupBox


def main():
    app = QApplication(sys.argv)

    window = QWidget()
    layout = QVBoxLayout(window)

    # 기존: box = QGroupBox("연락처")
    # 변경: 아래 한 줄만 교체
    box = CollapsibleGroupBox("연락처")

    form = QFormLayout(box)
    form.addRow("이름", QLineEdit())
    form.addRow("이메일", QLineEdit())
    form.addRow("전화", QLineEdit())

    layout.addWidget(box)

    # 접힘 상태가 바뀔 때 알림을 받고 싶다면:
    box.collapsedChanged.connect(lambda c: print("접힘 상태:", c))

    window.resize(320, 220)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
