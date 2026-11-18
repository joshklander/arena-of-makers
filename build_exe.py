"""Build the Arena of Makers Windows exes with PyInstaller.

Run on Windows with:  python build_exe.py
Or just double-click build_exe.bat, which does the pip installs first
and then runs this same build.

Builds, in the dist/ folder next to this file:
  ArenaOfMakers.exe         - the game, everything bundled in
  ArenaOfMakersUpdater.exe  - the updater, checks GitHub Releases

Your .env file is NOT bundled in and is NOT
touched. Put your own .env file next to the exes when you run them.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(command, what):
    print("\n" + what)
    print(" ".join(command))
    result = subprocess.run(command, cwd=HERE)
    if result.returncode != 0:
        print("FAILED: " + what)
        sys.exit(result.returncode)


def main():
    if sys.platform != "win32":
        print("This build is for Windows. Run it on a Windows computer,")
        print("where PyInstaller can build a Windows exe.")
        sys.exit(1)

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Run:")
        print("  pip install pyinstaller")
        print("Or double-click build_exe.bat, which installs it for you.")
        sys.exit(1)

    sounds_data = "sounds" + os.pathsep + "sounds"
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name",
            "ArenaOfMakers",
            "--add-data",
            sounds_data,
            # keyring finds its Windows backend at run time, so
            # name it here or the exe may not include it.
            "--hidden-import",
            "keyring.backends.Windows",
            "main.py",
        ],
        "Building the game exe...",
    )
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name",
            "ArenaOfMakersUpdater",
            "arena_of_makers_updater.py",
        ],
        "Building the updater exe...",
    )

    print("\nDone. Your exes are in the dist folder:")
    print("  dist\\ArenaOfMakers.exe")
    print("  dist\\ArenaOfMakersUpdater.exe")
    print("Put both exes in one folder, add your .env file next to them,")
    print("and double-click ArenaOfMakers.exe to play.")


if __name__ == "__main__":
    main()
