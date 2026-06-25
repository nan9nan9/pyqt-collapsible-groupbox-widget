"""CollapsibleGroupBox 기본 데모.

실행::

    python3 examples/basic_example.py

여러 개의 접이식 그룹박스를 세로로 배치한다. 각 그룹박스의 제목 줄을 클릭하면
접히거나 펴진다. 요약 위치(제목 오른쪽 / 박스 안쪽) 옵션과, 제목을 굵게/색상으로
꾸미는 두 가지 방법(HTML 제목 / 스타일시트)을 함께 보여준다.
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

    # 2) 접었을 때 요약을 제목 "오른쪽"에 표시 (SummaryBeside — 기본값)
    g_beside = CollapsibleGroupBox("연결 설정")
    g_beside.setSummaryEnabled(True)
    g_beside.setSummary("호스트 2 · 연결됨")
    g_beside.setSummaryPosition(CollapsibleGroupBox.SummaryBeside)  # 기본값이지만 명시
    QVBoxLayout(g_beside).addWidget(QCheckBox("자동 재연결"))
    g_beside.setCollapsed(True)
    outer.addWidget(g_beside)

    # 3) 접었을 때 요약을 박스 "안쪽" 줄에 표시 (SummaryInside)
    g_inside = CollapsibleGroupBox("고급 옵션")
    fi = QVBoxLayout(g_inside)
    spin_row = QHBoxLayout()
    spin_row.addWidget(QLabel("스레드 수:"))
    spin_row.addWidget(QSpinBox())
    fi.addLayout(spin_row)
    fi.addWidget(QCheckBox("실험적 기능 켜기"))
    g_inside.setSummaryEnabled(True)
    g_inside.setSummary("스레드 4 · 실험적 기능 OFF")
    g_inside.setSummaryPosition(CollapsibleGroupBox.SummaryInside)  # 박스 안쪽 줄에 요약
    g_inside.setCollapsed(True)
    outer.addWidget(g_inside)

    # 4) 제목을 굵게/색상으로 — 방법 A: HTML 제목(setTitle 에 태그를 넣으면 자동 인식)
    g_html = CollapsibleGroupBox(
        "<b>중요 설정</b> <font color='#e74c3c'>(주의)</font>"
    )
    QVBoxLayout(g_html).addWidget(QCheckBox("위험한 옵션 활성화"))
    outer.addWidget(g_html)

    # 5) 제목을 굵게/색상으로 — 방법 B: 스타일시트(QGroupBox::title)
    g_qss = CollapsibleGroupBox("프로필")
    g_qss.setStyleSheet(
        "QGroupBox::title { color: #2e86de; font-weight: bold; }"
    )
    QVBoxLayout(g_qss).addWidget(QCheckBox("공개 프로필"))
    outer.addWidget(g_qss)

    # 6) 접기/펴기 아이콘 모양 바꾸기 (셰브론 / 삼각형 / 플러스·마이너스)
    g_tri = CollapsibleGroupBox("삼각형 아이콘")
    g_tri.setArrowStyle(CollapsibleGroupBox.ArrowTriangle)
    QVBoxLayout(g_tri).addWidget(QCheckBox("옵션"))
    outer.addWidget(g_tri)

    g_pm = CollapsibleGroupBox("플러스·마이너스 아이콘")
    g_pm.setArrowStyle(CollapsibleGroupBox.ArrowPlusMinus)
    QVBoxLayout(g_pm).addWidget(QCheckBox("옵션"))
    outer.addWidget(g_pm)

    # 7) 아이콘 크기 키우기 (setArrowSize, 또는 환경변수 COLLAPSIBLE_ARROW_SIZE)
    g_big = CollapsibleGroupBox("큰 아이콘")
    g_big.setArrowSize(22)
    QVBoxLayout(g_big).addWidget(QCheckBox("옵션"))
    outer.addWidget(g_big)

    # 8) 애니메이션을 끈 그룹 + 외부 토글 버튼
    g3 = CollapsibleGroupBox("애니메이션 없음")
    g3.setAnimated(False)
    f3 = QVBoxLayout(g3)
    f3.addWidget(QLabel("이 그룹은 즉시 접히고 펴집니다."))
    outer.addWidget(g3)

    toggle_btn = QPushButton("위 '애니메이션 없음' 그룹 토글")
    toggle_btn.clicked.connect(g3.toggleCollapsed)
    outer.addWidget(toggle_btn)

    outer.addStretch(1)
    root.resize(380, 780)
    root.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
