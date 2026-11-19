"""Headless tests for arena_of_makers_updater.py (source mode).

wxPython is not needed: the updater's logic is plain functions,
and the window is only built when wx is installed. Run with:
    python test_updater.py

Covers the two updater fixes from 2026-11-18: a fresh install
lands in exactly one "Arena of Makers" folder (no nesting), and
the updater finds the real install — one level down, or in the
parent — so it offers "Check for updates" instead of "Install",
and a fresh install always writes its version note.
"""

import json
import os
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena_of_makers_updater as updater


def check(name, condition):
    if not condition:
        raise AssertionError("FAILED: " + name)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _make_game(folder, head="abc123"):
    """A folder that looks like an installed game."""
    _write(os.path.join(folder, "main.py"), "# game\n")
    _write(
        os.path.join(folder, updater.VERSION_FILE_NAME),
        json.dumps({"head_sha": head, "files": ["main.py"]}),
    )


def _make_zipball(path, files):
    """A fake GitHub zipball: top folder, then the game files."""
    top = "joshklander-arena-of-makers-abc1234"
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in files.items():
            zf.writestr(top + "/" + name, text)


def test_folder_normalisation():
    base = tempfile.mkdtemp()
    nested = os.path.join(
        base, "Arena of Makers", "Arena of Makers", "Arena of Makers"
    )
    check(
        "repeated Arena of Makers folders collapse to one",
        updater.normalise_install_folder(nested)
        == os.path.join(base, "Arena of Makers"),
    )
    plain = os.path.join(base, "Games")
    check(
        "a folder without the name is left alone",
        updater.normalise_install_folder(plain) == plain,
    )
    one = os.path.join(base, "Arena of Makers")
    check(
        "one Arena of Makers folder stays as it is",
        updater.normalise_install_folder(one) == one,
    )
    check(
        "an empty folder falls back to the default",
        updater.normalise_install_folder("") == updater.default_install_folder(),
    )

    # The default folder when the updater itself sits inside
    # a folder called Arena of Makers: that folder, not one
    # more level down.
    updater.SCRIPT_DIR = os.path.join(base, "Arena of Makers")
    try:
        check(
            "default folder is the folder the updater sits in",
            updater.default_install_folder()
            == os.path.join(base, "Arena of Makers"),
        )
    finally:
        updater.SCRIPT_DIR = os.path.dirname(
            os.path.abspath(updater.__file__)
        )
    print("Folder normalisation tests passed.")


def test_find_installed_folder():
    base = tempfile.mkdtemp()
    shown = os.path.join(base, "Arena of Makers")
    check("nothing installed anywhere returns None",
          updater.find_installed_folder(shown) is None)

    # The game one level down from the folder shown.
    _make_game(os.path.join(shown, "Arena of Makers"))
    check("the game one level down is found",
          updater.find_installed_folder(shown)
          == os.path.join(shown, "Arena of Makers"))

    # A version note on its own, with no main.py, is not a game.
    stray = os.path.join(base, "stray")
    os.makedirs(stray)
    _write(
        os.path.join(stray, updater.VERSION_FILE_NAME),
        json.dumps({"head_sha": "x", "files": []}),
    )
    check("a version note without main.py is not an install",
          updater.find_installed_folder(stray) is None)

    # The game in the shown folder itself.
    _make_game(shown)
    check("the game in the shown folder is found",
          updater.find_installed_folder(shown) == shown)
    check("is_installed needs main.py too",
          updater.is_installed(stray) is False
          and updater.is_installed(shown) is True)

    # The shown folder is the inner one; the game is in its parent.
    inner = os.path.join(base, "outer", "Arena of Makers")
    os.makedirs(inner)
    _make_game(os.path.join(base, "outer"))
    check("the game in the parent is found",
          updater.find_installed_folder(inner)
          == os.path.join(base, "outer"))
    print("Find installed folder tests passed.")


def test_install_from_zip():
    base = tempfile.mkdtemp()
    game_dir = os.path.join(base, "Arena of Makers")
    zip_path = os.path.join(base, "game.zip")
    _make_zipball(
        zip_path,
        {
            "main.py": "# game\n",
            "sounds/robot_laser.wav": "fake-wav",
            # .env is never in the repository, so it is never
            # in a zipball; the local one below must survive.
            "arena_version.json": "should be skipped\n",
        },
    )
    # A .env already on the computer must survive the install.
    _write(os.path.join(game_dir, ".env"), "SECRET=do-not-overwrite\n")
    log = []
    ok, message, installed = updater.install_from_zip(
        zip_path, game_dir, log.append
    )
    check("install from zip succeeds", ok is True and message == "")
    check("the game lands flat, not nested",
          os.path.exists(os.path.join(game_dir, "main.py"))
          and os.path.exists(
              os.path.join(game_dir, "sounds", "robot_laser.wav")))
    check("no nested top folder is created",
          not os.path.exists(
              os.path.join(game_dir, "joshklander-arena-of-makers-abc1234")))
    check("the version note is not written by the zip",
          not os.path.exists(
              os.path.join(game_dir, updater.VERSION_FILE_NAME)))
    check("the .env is left alone",
          open(os.path.join(game_dir, ".env"),
               encoding="utf-8").read() == "SECRET=do-not-overwrite\n")
    check("installed files are reported",
          installed == {"main.py", "sounds/robot_laser.wav"})
    print("Install from zip tests passed.")


def test_sync_game_writes_version_note():
    base = tempfile.mkdtemp()
    game_dir = os.path.join(base, "Arena of Makers")
    zip_path = os.path.join(base, "game.zip")
    _make_zipball(zip_path, {"main.py": "# game\n"})

    logs = []
    old_head = updater.get_head_sha
    old_tree = updater.get_tree
    old_download = updater.download_zipball
    try:
        updater.get_head_sha = lambda: "abc123"
        # The file list from GitHub is not available: the
        # install must still write its version note, from the
        # files it just installed.
        updater.get_tree = lambda: None

        def _fake_download(dest):
            shutil.copyfile(zip_path, dest)
            return True, ""

        updater.download_zipball = _fake_download
        result = updater.sync_game(game_dir, logs.append)
    finally:
        updater.get_head_sha = old_head
        updater.get_tree = old_tree
        updater.download_zipball = old_download
    check("a fresh install succeeds", result is True)
    check("a fresh install writes the version note",
          os.path.exists(
              os.path.join(game_dir, updater.VERSION_FILE_NAME)))
    head, _files = updater.load_state(game_dir)
    check("the version note holds the commit id", head == "abc123")
    check("the game is now found as installed",
          updater.find_installed_folder(game_dir) == game_dir)
    print("Sync game version note tests passed.")


def test_sync_game_uses_found_folder():
    base = tempfile.mkdtemp()
    # The game lives one level down from the folder shown.
    shown = os.path.join(base, "Arena of Makers")
    real = os.path.join(shown, "Arena of Makers")
    _make_game(real, head="abc123")

    logs = []
    old_head = updater.get_head_sha
    old_tree = updater.get_tree
    try:
        updater.get_head_sha = lambda: "abc123"
        updater.get_tree = lambda: [
            {"path": "main.py", "sha": updater.local_blob_hash(
                os.path.join(real, "main.py"))}
        ]
        result = updater.sync_game(shown, logs.append)
    finally:
        updater.get_head_sha = old_head
        updater.get_tree = old_tree
    check("sync against the folder one level down succeeds",
          result is True)
    check("sync says it found the game there",
          any("Found your game in" in line for line in logs))
    print("Sync game found folder tests passed.")


def test_updater_file_protection():
    """The updater's own file: the standalone updater never
    replaces it (it is running then), but the game's launch
    update may refresh it, so the backup never goes stale
    the way Makenna's old updater did in 2026-11-18.
    """
    base = tempfile.mkdtemp()
    game_dir = os.path.join(base, "Arena of Makers")
    _make_game(game_dir, head="abc123")
    _write(os.path.join(game_dir, "arena_of_makers_updater.py"),
           "# old updater\n")
    tree = [
        {"path": "main.py",
         "sha": updater.local_blob_hash(os.path.join(game_dir, "main.py"))},
        {"path": "arena_of_makers_updater.py",
         "sha": updater.blob_hash(b"# new updater\n")},
    ]

    # The standalone updater's own sync: the updater file is
    # skipped, so a running updater never replaces itself.
    to_download, _left, synced = updater.plan_sync(tree, game_dir)
    check("standalone sync skips the updater file",
          all(e["path"] != "arena_of_makers_updater.py"
              for e in to_download)
          and "arena_of_makers_updater.py" not in synced)

    # The game's launch update: the updater file is compared
    # and synced like any other file.
    to_download, _left, synced = updater.plan_sync(
        tree, game_dir, include_updater=True)
    check("game sync offers the new updater file",
          any(e["path"] == "arena_of_makers_updater.py"
              for e in to_download)
          and "arena_of_makers_updater.py" in synced)

    # A fresh install from a zipball: the standalone install
    # skips the updater file, the game's install takes it.
    zip_path = os.path.join(base, "game.zip")
    _make_zipball(zip_path, {
        "main.py": "# game\n",
        "arena_of_makers_updater.py": "# new updater\n",
    })
    fresh = os.path.join(base, "Fresh")
    log = []
    ok, _message, installed = updater.install_from_zip(
        zip_path, fresh, log.append)
    check("standalone install skips the updater file",
          ok is True
          and not os.path.exists(
              os.path.join(fresh, "arena_of_makers_updater.py")))
    ok, _message, installed = updater.install_from_zip(
        zip_path, fresh, log.append, include_updater=True)
    check("game install takes the updater file",
          ok is True
          and os.path.exists(
              os.path.join(fresh, "arena_of_makers_updater.py"))
          and "arena_of_makers_updater.py" in installed)
    print("Updater file protection tests passed.")


def test_sync_game_updates_updater():
    """End to end, headless: the game's sync replaces the
    old updater file, and the standalone sync leaves it
    alone. The launcher .bat stays protected either way.
    """
    base = tempfile.mkdtemp()
    game_dir = os.path.join(base, "Arena of Makers")
    _make_game(game_dir, head="oldhead")
    _write(os.path.join(game_dir, "arena_of_makers_updater.py"),
           "# old updater\n")
    _write(os.path.join(game_dir, "run_arena_of_makers_updater.bat"),
           "old launcher\n")
    new_updater = b"# new updater\n"
    contents = {
        "main.py": b"# game\n",
        "arena_of_makers_updater.py": new_updater,
    }
    tree = [
        {"path": path, "sha": updater.blob_hash(data)}
        for path, data in contents.items()
    ]

    logs = []
    old_head = updater.get_head_sha
    old_tree = updater.get_tree
    old_download = updater.download_file
    try:
        updater.get_head_sha = lambda: "newhead"
        updater.get_tree = lambda: tree

        def _fake_download(path, sha, size, dest):
            with open(dest, "wb") as handle:
                handle.write(contents[path])
            return True, ""

        updater.download_file = _fake_download

        # Standalone first: the updater file is untouched.
        result = updater.sync_game(game_dir, logs.append)
        check("standalone sync succeeds", result is True)
        check("standalone sync leaves the updater file alone",
              open(os.path.join(
                  game_dir, "arena_of_makers_updater.py"),
                  encoding="utf-8").read() == "# old updater\n")

        # The game's sync: the updater file is refreshed,
        # the launcher .bat is still left alone.
        result = updater.sync_game(
            game_dir, logs.append, include_updater=True)
        check("game sync succeeds", result is True)
        check("game sync refreshes the updater file",
              open(os.path.join(
                  game_dir, "arena_of_makers_updater.py"),
                  encoding="utf-8").read() == "# new updater\n")
        check("game sync still leaves the launcher alone",
              open(os.path.join(
                  game_dir, "run_arena_of_makers_updater.bat"),
                  encoding="utf-8").read() == "old launcher\n")
        head, _files = updater.load_state(game_dir)
        check("the version note holds the new commit id",
              head == "newhead")
    finally:
        updater.get_head_sha = old_head
        updater.get_tree = old_tree
        updater.download_file = old_download
    print("Sync game updates updater tests passed.")


if __name__ == "__main__":
    test_folder_normalisation()
    test_find_installed_folder()
    test_install_from_zip()
    test_sync_game_writes_version_note()
    test_sync_game_uses_found_folder()
    test_updater_file_protection()
    test_sync_game_updates_updater()
    print("\nAll updater tests passed.")
