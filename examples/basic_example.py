"""CollapsibleGroupBox 기본 데모.

실행::

    python3 examples/basic_example.py

여러 개의 접이식 그룹박스를 세로로 배치한다. 각 그룹박스의 제목(셰브론 화살표)을
클릭하면 접히거나 펴진다. 두 번째 박스는 접힌 상태로 시작한다.
"""

import os
import sys

# 설치 없이 바로 실행할 수 있도록 src 를 import 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from qtpy.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QLineEdit, QPushButton, QSpinBox,
)

from collapsible_groupbox import CollapsibleGroupBox


def main():
    app = QApplication(sys.argv)

    root = QWidget()
    root.setWindowTitle("CollapsibleGroupBox 데모")
    outer = QVBoxLayout(root)

    # 1) 일반 옵션 그룹
    g1 = CollapsibleGroupBox("일반 설정")
    f1 = QVBoxLayout(g1)
    f1.addWidget(QCheckBox("자동 저장 사용"))
    f1.addWidget(QCheckBox("시작 시 마지막 파일 열기"))
    row = QHBoxLayout()
    row.addWidget(QLabel("이름:"))
    row.addWidget(QLineEdit())
    f1.addLayout(row)
    outer.addWidget(g1)

    # 2) 고급 옵션 그룹 — 접힌 상태로 시작
    g2 = CollapsibleGroupBox("고급 설정")
    f2 = QVBoxLayout(g2)
    spin_row = QHBoxLayout()
    spin_row.addWidget(QLabel("스레드 수:"))
    spin_row.addWidget(QSpinBox())
    f2.addLayout(spin_row)
    f2.addWidget(QCheckBox("실험적 기능 켜기"))
    g2.setCollapsed(True)
    outer.addWidget(g2)

    # 3) 애니메이션을 끈 그룹 + 외부 토글 버튼
    g3 = CollapsibleGroupBox("애니메이션 없음")
    g3.setAnimated(False)
    f3 = QVBoxLayout(g3)
    f3.addWidget(QLabel("이 그룹은 즉시 접히고 펴집니다."))
    outer.addWidget(g3)

    toggle_btn = QPushButton("위 '애니메이션 없음' 그룹 토글")
    toggle_btn.clicked.connect(g3.toggleCollapsed)
    outer.addWidget(toggle_btn)

    outer.addStretch(1)
    root.resize(360, 480)
    root.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
