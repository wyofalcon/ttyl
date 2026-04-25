"""TTYL entry point - tray icon + Qt event loop."""

import sys

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


def main() -> int:
    QCoreApplication.setApplicationName("TTYL")
    QCoreApplication.setOrganizationName("TTYL")

    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)

    tray = QSystemTrayIcon(QIcon.fromTheme("appointment"))
    tray.setToolTip("TTYL")

    menu = QMenu()
    quit_action = QAction("Quit", menu)
    quit_action.triggered.connect(qapp.quit)
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.show()

    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
