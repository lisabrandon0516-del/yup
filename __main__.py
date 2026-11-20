"""Launch the Back Office: Retail desk."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from open_late.ui.theme import load_fonts, set_family, stylesheet
from open_late.ui.window import MainWindow


def main() -> int:
    # The playable build starts new live-economy games with the three AI rival
    # chains. Library and test callers keep the default (off, Northline).
    from open_late.rival_ai import set_default_enabled

    set_default_enabled(True)
    from open_late.shelves import set_default_enabled as shelves_default_enabled

    shelves_default_enabled(True)  # new corporate games start with store layouts on
    from open_late.shopperlife import set_default_enabled as shoppers_default_enabled

    shoppers_default_enabled(True)  # a played game keeps a household population
    app = QApplication(sys.argv)
    from open_late import GAME_NAME

    app.setApplicationName(GAME_NAME)
    app.setStyle("Fusion")
    family = load_fonts()
    set_family(family)
    app.setStyleSheet(stylesheet(family))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
