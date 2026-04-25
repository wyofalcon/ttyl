"""PyInstaller build script for TTYL. Uses the library API (no shell)."""

from pathlib import Path

import PyInstaller.__main__


def main() -> None:
    here = Path(__file__).parent
    icon_path = here / "ttyl" / "assets" / "tray-icon.ico"
    args = [
        "--name", "TTYL",
        "--onefile",
        "--windowed",
        str(here / "ttyl" / "__main__.py"),
    ]
    if icon_path.exists():
        args[3:3] = ["--icon", str(icon_path)]
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    main()
