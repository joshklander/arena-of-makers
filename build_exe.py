"""Build the Arena of Makers Windows exes with PyInstaller.

Run on Windows with:  python build_exe.py v1.0.1
Or just double-click build_exe.bat, which does the pip installs first
and then runs this same build. Without a version on the command line,
it asks for one.

The version is the GitHub Release tag these exes will be published
as, like v1.0.1. It is baked into both exes, so a fresh exe knows
which Release it is and is not offered that same Release again.
Use the same tag when you make the Release.

Builds, in the dist/ folder next to this file:
  ArenaOfMakers.exe         - the game, everything bundled in
  ArenaOfMakersUpdater.exe  - the updater, checks GitHub Releases

Your .env file is NOT bundled in and is NOT
touched. Put your own .env file next to the exes when you run them.
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION_MODULE = os.path.join(HERE, "build_version.py")
VERSION_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")


def ask_version(argv):
    """The Release tag for this build, from the command line or asked."""
    version = argv[1].strip() if len(argv) > 1 else ""
    while not VERSION_PATTERN.match(version):
        if version:
            print("That is not a version like v1.0.1. Try again.")
        version = input(
            "Version for this build, the GitHub Release tag, like v1.0.1: "
        ).strip()
    return version


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

    version = ask_version(sys.argv)
    # A tiny module just for the build: the updater imports it, so
    # PyInstaller puts it inside both exes. It is removed afterwards
    # and never goes in the repository.
    with open(VERSION_MODULE, "w", encoding="utf-8") as handle:
        handle.write('"""Made by build_exe.py. Do not edit or commit."""\n')
        handle.write("VERSION = %r\n" % version)
    try:
        build_both()
    finally:
        try:
            os.remove(VERSION_MODULE)
        except OSError:
            pass

    print("\nDone. Your %s exes are in the dist folder:" % version)
    print("  dist\\ArenaOfMakers.exe")
    print("  dist\\ArenaOfMakersUpdater.exe")
    print("Put both exes in one folder, add your .env file next to them,")
    print("and double-click ArenaOfMakers.exe to play.")
    print("Publish them as the GitHub Release %s, with that exact tag." % version)


def build_both():
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


if __name__ == "__main__":
    main()
