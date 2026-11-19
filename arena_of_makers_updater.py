"""Arena of Makers updater - install the game or pull the latest version.

Accessible wxPython window, built for screen reader users (NVDA / VoiceOver):
every action is a native focusable button and every result is plain text.

How it works
------------
- You pick an install folder. If the game is not there yet, the updater
  downloads the whole game from GitHub and installs it.
- If the game is already there, it asks GitHub for the newest version and
  downloads the whole game as one zip file, then unpacks it over the
  game folder (Phase 31). It used to download each changed file with
  its own GitHub API call; with 78 files in the repo and only 60 free
  unauthenticated API calls an hour, a big update could hit the limit
  halfway, stop, and leave a mix of old and new files — and the next
  launch would offer the same update again and start over. One zip
  is one download, so the limit cannot stop it halfway, and nothing
  on disk is touched until the whole download has arrived.
- Files that are only on your computer, such as saves and settings, are
  never deleted and never overwritten. The updater only ever writes files
  that are in the repository, and it never deletes anything at all. If a
  file leaves the game, your local copy is simply left in place.
- No token, no sign-in, no typing commands. One window, a few buttons.

Why there is no token
----------------------
The Arena of Makers repository on GitHub is public, so anyone can read it
without signing in. This updater uses the public GitHub API with no
account and no token. There is no token to paste, no token file, and
nothing secret anywhere in this program. GitHub allows 60 free
unauthenticated requests an hour; if you ever see a message about the
limit, just wait an hour and try again.

The updater itself is not updated by this program. When a new updater
comes out, download it again from the repository or from Google Drive
and replace this file.

Exe mode
--------
When this updater is itself a frozen exe (built by the GitHub
workflow, next to ArenaOfMakers.exe), it does NOT sync source files.
Instead it checks the latest GitHub Release, downloads the new
ArenaOfMakers.exe, and swaps it in for the old one. Your .env file
lives next to the exe and is never touched.
The game must be closed first: Windows will not let a running exe
be replaced, so the updater says so plainly and you press the
button again after closing the game.
"""

import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import zipfile

try:
    import wx
except ImportError:  # pragma: no cover - the logic below still works headless
    wx = None

REPO = "joshklander/arena-of-makers"
API_BASE = "https://api.github.com/repos/" + REPO
# The folder the updater sits in. In the exe that is the folder
# holding ArenaOfMakersUpdater.exe, not the temporary folder a
# one-file exe unpacks into (which is deleted on close), so the
# updater remembers its folder between runs. This file is used on
# its own, so it does not import supabase_config.app_folder; the
# rule is the same.
if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FOLDER_STATE_FILE = os.path.join(SCRIPT_DIR, "arena_updater_state.json")
VERSION_FILE_NAME = "arena_version.json"
GAME_FOLDER_NAME = "Arena of Makers"

# Files the updater itself uses. They are never written by the
# updater's own sync, even if a future version of the
# repository ever listed them, because overwriting the program
# while it is running could break it. That protection is what
# left Makenna's computer on the old updater in 2026-11-18:
# the fixed updater was on GitHub, but her copy could never
# fetch it, so none of the fixes reached her. The game may
# refresh the updater's .py file (see _is_protected): the
# updater is not running while the game updates, so the
# backup updater never goes stale. The launcher .bat, the
# updater's own folder-choice state, and the version note
# stay protected always.
PROTECTED_FILES = {
    "arena_of_makers_updater.py",
    "run_arena_of_makers_updater.bat",
    "arena_updater_state.json",
    VERSION_FILE_NAME,
}


# Files a sync never downloads, in either direction, in any mode.
# arena_log.txt is tracked in the repo so Makenna and Josh (and their
# assistants) can both see errors in it — push_arena_changes.py sends
# the local log UP to GitHub on purpose — but the updater must never
# download GitHub's copy DOWN over the local one. The local log is
# always newer than the repo copy (it keeps growing while the game
# runs), so the old per-file sync re-downloaded it on every update
# and would have wiped the local diagnostics. It is also why a
# hand-installed copy with no version note was always offered an
# update: the log alone always differed. The game creates the log
# itself, so a fresh install does not need the repo's copy either.
NEVER_SYNC_FILES = {
    "arena_log.txt",
}


def _is_never_sync(path):
    """True when a file must never be written by a sync."""
    return path in NEVER_SYNC_FILES


def _is_protected(path, include_updater=False):
    """True when a sync must leave a file alone.

    With include_updater False (the standalone updater's own
    sync, and the default), every protected file is left
    alone. With include_updater True (the game's launch
    update, Phase 19), only the updater's .py file may be
    refreshed: the updater is not running then, and keeping
    it current is what keeps the backup working. Its
    launcher .bat, its folder-choice state, and the version
    note are never written by a sync either way — the note
    is written by save_state, not by downloading it."""
    if path not in PROTECTED_FILES:
        return False
    return not (
        include_updater and path == "arena_of_makers_updater.py"
    )


def normalise_install_folder(folder):
    """One "Arena of Makers" folder, never a nest of them.

    A fresh install once wanted Arena of Makers inside Arena
    of Makers inside Arena of Makers (2026-11-18): the default
    added the name even when the updater was already sitting
    inside a folder with that name, and a manual zip
    extraction could add another level. Collapsing repeated
    trailing folders of that name fixes both, and keeps a
    folder the player picked by hand as they picked it."""
    folder = (folder or "").strip()
    if not folder:
        folder = os.path.join(SCRIPT_DIR, GAME_FOLDER_NAME)
    folder = os.path.abspath(folder)
    parts = folder.split(os.sep)
    while (
        len(parts) > 1
        and parts[-1].lower() == GAME_FOLDER_NAME.lower()
        and parts[-2].lower() == GAME_FOLDER_NAME.lower()
    ):
        parts.pop()
    return os.sep.join(parts)


def default_install_folder():
    """Where the game goes unless the user picks somewhere else.

    If the updater already sits inside a folder called Arena
    of Makers, that folder is the install folder — appending
    the name again would nest it one level deeper."""
    return normalise_install_folder(
        os.path.join(SCRIPT_DIR, GAME_FOLDER_NAME)
    )


def load_folder_choice():
    """Return the install folder the user picked before, or the default."""
    try:
        with open(FOLDER_STATE_FILE, "r", encoding="utf-8") as f:
            folder = json.load(f).get("install_folder")
        if folder:
            return normalise_install_folder(folder)
    except (OSError, ValueError, AttributeError):
        pass
    return default_install_folder()


def save_folder_choice(folder):
    try:
        with open(FOLDER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"install_folder": normalise_install_folder(folder)}, f)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# GitHub API helpers (plain urllib, no extra packages, no token needed)
# --------------------------------------------------------------------------

def api_get(path, timeout=60):
    """GET one public API path. Returns (status, payload dict or list).

    Status 403 usually means GitHub's free limit for unsigned-in requests
    was reached. Status 404 means the thing asked for is not there.
    The timeout is short for the game's launch check, so a slow
    GitHub never holds up starting the game; the updater's own
    sync keeps the slower default.
    """
    url = API_BASE + path
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "ArenaOfMakersUpdater")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            payload = {"message": "GitHub answered with an error."}
        return e.code, payload
    except Exception as e:
        return 0, {"message": "Could not reach GitHub: %s" % e}


def get_head_sha(timeout=60):
    """Return the newest commit id on main, or None when it cannot be read."""
    status, payload = api_get("/git/refs/heads/main", timeout=timeout)
    if status == 200:
        return payload.get("object", {}).get("sha")
    return None


def get_tree(timeout=60):
    """Return the full file list of main, or None when it cannot be read.

    Each entry has path, sha (the git blob id) and size.
    """
    status, payload = api_get("/git/trees/main?recursive=1", timeout=timeout)
    if status == 200 and isinstance(payload, dict):
        return [t for t in payload.get("tree", []) if t.get("type") == "blob"]
    return None


# --------------------------------------------------------------------------
# GitHub Release helpers (exe mode only)
# --------------------------------------------------------------------------

RELEASES_URL = API_BASE + "/releases/latest"
GAME_EXE_NAME = "ArenaOfMakers.exe"
UPDATER_EXE_NAME = "ArenaOfMakersUpdater.exe"


def get_latest_release(timeout=60):
    """Return (tag, asset download url for the game exe), or (None, None)."""
    status, payload = api_get("/releases/latest", timeout=timeout)
    if status != 200 or not isinstance(payload, dict):
        return None, None
    for asset in payload.get("assets", []):
        if asset.get("name") == GAME_EXE_NAME:
            return payload.get("tag_name"), asset.get("browser_download_url")
    return payload.get("tag_name"), None


def local_exe_version_file(game_dir):
    return os.path.join(game_dir, "arena_version.json")


def update_exe_from_release(game_dir, log):
    """Download the newest game exe from GitHub Releases and swap it in.

    Returns True when the game exe now matches the latest release.
    Never touches .env or arena_log.txt. There is no local save file.
    """
    game_dir = os.path.abspath(game_dir)
    game_exe = os.path.join(game_dir, GAME_EXE_NAME)
    tag, download_url = get_latest_release()
    if tag is None:
        log("Could not reach GitHub to check for updates. Try again later.")
        return False
    if download_url is None:
        log("The latest release has no game exe yet. Try again later.")
        return False
    # Remember which release we already have, in the same version file
    # the source updater uses, so a later check is quick.
    stored_head, _files = load_state(game_dir)
    if stored_head == tag and os.path.exists(game_exe):
        log("You already have the newest version (%s). Nothing to download." % tag)
        return True
    log("A newer version is on GitHub (%s). Downloading the new game." % tag)
    tmp = os.path.join(tempfile.gettempdir(), GAME_EXE_NAME)
    req = urllib.request.Request(download_url, method="GET")
    req.add_header("User-Agent", "ArenaOfMakersUpdater")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            with open(tmp, "wb") as f:
                shutil.copyfileobj(resp, f)
    except Exception as e:
        log("Could not download the new game: %s" % e)
        return False
    # Windows will not replace a running exe. Try the swap; if it
    # fails, say so plainly instead of deleting anything.
    try:
        os.makedirs(game_dir, exist_ok=True)
        if os.path.exists(game_exe):
            os.replace(tmp, game_exe)
        else:
            shutil.move(tmp, game_exe)
    except OSError:
        log("Close Arena of Makers first, then press Check for updates again. "
            "The new version is downloaded and ready to install.")
        return False
    save_state(game_dir, tag, {GAME_EXE_NAME})
    log("Update finished. You now have %s. Your save and your .env file were left alone." % tag)
    return True


def blob_hash(data):
    """The git blob id of some bytes, so a local file can be compared."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def local_blob_hash(path):
    try:
        with open(path, "rb") as f:
            return blob_hash(f.read())
    except OSError:
        return None


def download_file(path, sha, size, dest):
    """Download one repository file to dest. Returns (ok, message).

    Files under 1 MB come from the contents API; larger ones come from the
    blob API, because the contents API refuses to return big files.

    Kept for one-off use. sync_game no longer calls it (Phase 31):
    an update downloads the whole game as one zipball instead, so a
    big update cannot run out of GitHub's 60 free unauthenticated
    API calls an hour halfway through and leave a half-updated game.
    """
    if size is not None and size < 1000000:
        status, payload = api_get("/contents/" + urllib.parse.quote(path))
        if status != 200:
            return False, "Could not download %s." % path
        raw = base64.b64decode(payload["content"])
    else:
        status, payload = api_get("/git/blobs/" + sha)
        if status != 200:
            return False, "Could not download %s." % path
        raw = base64.b64decode(payload["content"])
    if blob_hash(raw) != sha:
        return False, "Downloaded %s did not match GitHub. Try again." % path
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(raw)
    return True, ""


# --------------------------------------------------------------------------
# Sync planning and applying
# --------------------------------------------------------------------------

def version_path(game_dir):
    return os.path.join(game_dir, VERSION_FILE_NAME)


def load_state(game_dir):
    """Read the last synced commit id and file list, or an empty state."""
    try:
        with open(version_path(game_dir), "r", encoding="utf-8") as f:
            state = json.load(f)
        return state.get("head_sha"), set(state.get("files", []))
    except (OSError, ValueError, AttributeError):
        return None, set()


def save_state(game_dir, head_sha, files):
    try:
        os.makedirs(game_dir, exist_ok=True)
        with open(version_path(game_dir), "w", encoding="utf-8") as f:
            json.dump({"head_sha": head_sha, "files": sorted(files)}, f)
        return True
    except OSError:
        return False


def _folder_has_game(folder):
    """True when a folder holds a real install: the version
    note the updater writes, plus main.py. The note alone is
    not enough — a stray note in the wrong folder used to make
    the updater think a game was installed when it was not."""
    return (
        os.path.exists(version_path(folder))
        and os.path.exists(os.path.join(folder, "main.py"))
    )


def is_installed(game_dir):
    """True when this folder already has a game installed by this updater."""
    return _folder_has_game(game_dir)


def find_installed_folder(folder):
    """Find the folder holding an installed game, or None.

    The folder shown may not be the one the game ended up in:
    after the nested-folder mess the version note could sit
    one level down, in <folder>/Arena of Makers, or the shown
    folder could itself be the inner one while the game sits
    in its parent. Checks the shown folder, one level down,
    and the parent, in that order. Returns the folder that
    holds the game, so the updater can point at it and offer
    "Check for updates" instead of "Install"."""
    folder = normalise_install_folder(folder)
    candidates = [folder, os.path.join(folder, GAME_FOLDER_NAME)]
    parent = os.path.dirname(folder)
    if parent and parent != folder:
        candidates.append(parent)
    seen = set()
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if candidate in seen:
            continue
        seen.add(candidate)
        if _folder_has_game(candidate):
            return candidate
    return None


def plan_sync(tree, game_dir, include_updater=False):
    """Compare the repository file list with the local folder.

    Returns (to_download, left_in_place, synced_files). to_download is a
    list of tree entries that are missing or different locally.
    left_in_place is a list of files that were synced before but are no
    longer in the repository; they are never deleted, only reported.
    synced_files is the full set of files the sync will leave in place.
    With include_updater True, the updater's own .py file is
    compared and synced like any other file (the game's
    launch update); with False, it is left alone (the
    standalone updater's own sync, which is running then).
    """
    _head, previous_files = load_state(game_dir)
    to_download = []
    synced_files = set()
    for entry in tree:
        path = entry["path"]
        if _is_never_sync(path):
            # Never compared, never downloaded: the local
            # arena_log.txt is always newer than the repo's.
            continue
        if _is_protected(path, include_updater):
            continue
        synced_files.add(path)
        local = os.path.join(game_dir, path)
        if local_blob_hash(local) != entry["sha"]:
            to_download.append(entry)
    left_in_place = []
    for path in sorted(previous_files):
        if _is_never_sync(path):
            continue
        if _is_protected(path, include_updater):
            continue
        if path not in synced_files and os.path.exists(os.path.join(game_dir, path)):
            left_in_place.append(path)
    return to_download, left_in_place, synced_files


def download_zipball(dest):
    """Download the whole repository as one zip. Returns (ok, message)."""
    req = urllib.request.Request(API_BASE + "/zipball/main", method="GET")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "ArenaOfMakersUpdater")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            with open(dest, "wb") as f:
                shutil.copyfileobj(resp, f)
        return True, ""
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, ("GitHub did not answer the download. The free "
                           "limit may have been reached. Try again in an hour.")
        return False, "GitHub answered with an error while downloading."
    except Exception as e:
        return False, "Could not download the game: %s" % e


def install_from_zip(zip_path, game_dir, log, include_updater=False):
    """Unpack a GitHub zipball into the game folder.

    Returns (ok, message, installed_files). Files are copied
    over one by one. Nothing already in the folder is ever
    removed, so saves, settings and any other local-only files
    survive an install untouched. The zipball's top folder is
    stripped, so the game lands flat in the folder given, not
    nested one level deeper. installed_files is the set of
    files written, so a fresh install can write its version
    note even when the file list from GitHub is not available.
    With include_updater True, the updater's own .py file is
    installed too (the game's launch update); with False it
    is left alone (the standalone updater's own install,
    which is running then).
    The download is checked (testzip) and fully extracted to
    a temporary folder BEFORE anything is copied into the
    game folder, so a damaged or incomplete download touches
    nothing. The local arena_log.txt is never written, in
    either mode: the zip's copy is skipped and the local
    diagnostics stay in place.
    """
    installed = set()
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            if not names:
                return False, "The downloaded game file was empty.", installed
            top = names[0].split("/")[0]
            if zf.testzip() is not None:
                return False, "The downloaded game file was damaged.", installed
            rel_names = {
                name[len(top) + 1:].replace("/", os.sep)
                for name in names
                if name.startswith(top + "/") and not name.endswith("/")
            }
            if "main.py" not in rel_names:
                return False, ("The downloaded game file did not "
                               "contain the game."), installed
            tmpdir = tempfile.mkdtemp(prefix="arena-makers-install-")
            try:
                zf.extractall(tmpdir)
                src = os.path.join(tmpdir, top)
                for root, _dirs, files in os.walk(src):
                    for name in files:
                        s = os.path.join(root, name)
                        rel = os.path.relpath(s, src)
                        rel_slash = rel.replace(os.sep, "/")
                        if _is_never_sync(rel_slash):
                            continue
                        if _is_protected(rel_slash, include_updater):
                            continue
                        d = os.path.join(game_dir, rel)
                        os.makedirs(os.path.dirname(d), exist_ok=True)
                        shutil.copy2(s, d)
                        installed.add(rel.replace(os.sep, "/"))
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
        return True, "", installed
    except Exception as e:
        return False, "Could not unpack the game: %s" % e, installed


def sync_game(game_dir, log, include_updater=False):
    """Install the game or bring it up to date. Runs in a worker thread.

    log(text) is called with plain-word progress lines. Returns True when
    the local game now matches GitHub, False otherwise. With
    include_updater True (the game's launch update), the
    updater's own .py file is synced too, so the backup
    updater never goes stale; with False (the standalone
    updater's own sync, and the default) it is left alone,
    because the updater is running then.

    Phase 31: an update downloads the whole game as ONE zipball
    (download_zipball + install_from_zip, the same path a fresh
    install already used), instead of one GitHub API call per
    changed file. That is 3 API calls in total for an update —
    head, tree, zipball — however many files changed, so the
    60-calls-an-hour unauthenticated limit cannot stop it
    halfway. Nothing on disk is touched until the whole zip
    has downloaded and passed its damage check, and the
    version note is only saved after the unpack succeeds, so
    a failed update leaves the old game whole and the old
    version note in place: the next launch simply offers the
    same update again and tries once more, instead of
    re-downloading a half-updated game from scratch.
    """
    # Frozen exe mode: update the bundled exe from GitHub Releases,
    # never by syncing source files over it.
    if getattr(sys, "frozen", False):
        return update_exe_from_release(game_dir, log)
    game_dir = normalise_install_folder(game_dir)
    # The game may be installed one level down, or in the
    # parent, after the nested-folder mess: find it and use
    # that folder, so an update runs against the real game.
    found = find_installed_folder(game_dir)
    if found is not None:
        if found != game_dir:
            log("Found your game in %s. Using that folder." % found)
        game_dir = found
    installed = found is not None
    head = get_head_sha()
    if head is None:
        log("Could not reach GitHub to check for updates. Try again later.")
        return False

    if not installed:
        log("Arena of Makers is not installed here yet. Downloading the whole game.")
        tmp = os.path.join(tempfile.gettempdir(), "arena-of-makers-install.zip")
        ok, message = download_zipball(tmp)
        if not ok:
            log(message)
            return False
        try:
            ok, message, installed_files = install_from_zip(
                tmp, game_dir, log, include_updater
            )
            if not ok:
                log(message)
                return False
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        # Always write the version note, so the next launch
        # offers "Check for updates" instead of "Install".
        # The file list from GitHub is preferred; when it is
        # not available, the files just installed will do.
        tree = get_tree()
        if tree is not None:
            files = {
                e["path"]
                for e in tree
                if not _is_never_sync(e["path"])
                and not _is_protected(e["path"], include_updater)
            }
        else:
            files = installed_files
        if not save_state(game_dir, head, files):
            log("Installed the game, but could not save the version "
                "note, so the updater may offer to install again. "
                "Try running the updater once more.")
            return False
        log("Arena of Makers is installed in %s. You can play it now."
            % game_dir)
        return True

    stored_head, _files = load_state(game_dir)
    if stored_head != head:
        log("A newer version is on GitHub. Checking which files changed.")
    tree = get_tree()
    if tree is None:
        log("Could not read the file list from GitHub. Try again later.")
        return False
    to_download, left_in_place, synced_files = plan_sync(
        tree, game_dir, include_updater
    )
    if not to_download:
        save_state(game_dir, head, synced_files)
        for path in left_in_place:
            log("%s is no longer in the game, but your copy was left in place." % path)
        log("You already have the newest version. Nothing to download.")
        return True
    # One download for the whole update, however many files
    # changed. Nothing on disk is touched until the zip has
    # fully downloaded: if this fails, the old game and the
    # old version note are both still in place, and the next
    # launch simply offers the update again.
    if stored_head == head:
        log("Some game files were missing or different. "
            "Downloading the new version as one file.")
    else:
        log("Downloading the new version as one file "
            "(%d files changed)." % len(to_download))
    tmp = os.path.join(tempfile.gettempdir(), "arena-of-makers-update.zip")
    ok, message = download_zipball(tmp)
    if not ok:
        log(message)
        return False
    try:
        ok, message, _installed_files = install_from_zip(
            tmp, game_dir, log, include_updater
        )
        if not ok:
            log(message)
            return False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if not os.path.exists(os.path.join(game_dir, "main.py")):
        log("The update did not leave a working game behind. "
            "Your old files were left in place. Try again.")
        return False
    for path in left_in_place:
        log("%s is no longer in the game, but your copy was left in place." % path)
    if not save_state(game_dir, head, synced_files):
        log("Updated the game, but could not save the version note.")
        return False
    log("Update finished. %d files changed." % len(to_download))
    return True


# --------------------------------------------------------------------------
# Accessible window
# --------------------------------------------------------------------------

if wx is not None:  # pragma: no cover - needs a display and wxPython

    class UpdaterFrame(wx.Frame):
        """One window: pick a folder, then install or update."""

        def __init__(self):
            super().__init__(None, title="Arena of Makers Updater", size=(640, 560))
            panel = wx.Panel(self)
            sizer = wx.BoxSizer(wx.VERTICAL)

            self.title = wx.StaticText(
                panel, label="Arena of Makers Updater")
            sizer.Add(self.title, 0, wx.ALL, 10)

            self.status = wx.StaticText(panel, label="")
            self.status.Wrap(600)
            sizer.Add(self.status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

            folder_label = wx.StaticText(panel, label="Install folder:")
            sizer.Add(folder_label, 0, wx.LEFT | wx.RIGHT, 10)
            folder_row = wx.BoxSizer(wx.HORIZONTAL)
            self.folder_field = wx.TextCtrl(panel, size=(440, -1))
            self.folder_field.Bind(wx.EVT_TEXT, self.on_folder_typed)
            folder_row.Add(self.folder_field, 0, wx.ALL, 5)
            self.choose_button = wx.Button(panel, label="Choose folder")
            self.choose_button.Bind(wx.EVT_BUTTON, self.on_choose_folder)
            folder_row.Add(self.choose_button, 0, wx.ALL, 5)
            sizer.Add(folder_row, 0, wx.LEFT | wx.RIGHT, 5)

            self.action_button = wx.Button(panel, label="Check for updates")
            self.action_button.Bind(wx.EVT_BUTTON, self.on_action)
            sizer.Add(self.action_button, 0, wx.ALL, 5)
            self.close_button = wx.Button(panel, label="Close")
            self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
            sizer.Add(self.close_button, 0, wx.ALL, 5)
            self.log = wx.TextCtrl(
                panel,
                style=wx.TE_MULTILINE | wx.TE_READONLY, size=(600, 260))
            sizer.Add(self.log, 0, wx.ALL, 5)

            panel.SetSizer(sizer)
            self.game_dir = load_folder_choice()
            self.folder_field.SetValue(self.game_dir)
            self.working = False
            self.refresh_status()
            self.action_button.SetFocus()
            self.Centre()
            self.Show()

        def refresh_status(self):
            found = find_installed_folder(self.game_dir)
            if found is not None:
                if found != os.path.abspath(self.game_dir):
                    # The game was one level down, or in the
                    # parent: point the folder box at it, so the
                    # next launch finds it straight away.
                    self.game_dir = found
                    self.folder_field.SetValue(found)
                    save_folder_choice(found)
                _head, files = load_state(found)
                self.status.SetLabel(
                    "Arena of Makers is installed in %s "
                    "(%d files)." % (found, len(files)))
                self.action_button.SetLabel("Check for updates")
            else:
                self.status.SetLabel(
                    "Arena of Makers is not installed in %s yet. "
                    "The updater looked for the version note and "
                    "main.py there, and one folder down, and did "
                    "not find them." % self.game_dir)
                self.action_button.SetLabel("Install Arena of Makers")

        def say(self, text):
            wx.CallAfter(self.log.AppendText, text + "\n")

        def set_working(self, working):
            self.working = working
            self.action_button.Enable(not working)
            self.choose_button.Enable(not working)
            self.folder_field.Enable(not working)

        def on_folder_typed(self, _event):
            self.game_dir = normalise_install_folder(
                self.folder_field.GetValue())
            save_folder_choice(self.game_dir)
            self.refresh_status()

        def on_choose_folder(self, _event):
            dlg = wx.DirDialog(
                self, "Choose where to install Arena of Makers",
                defaultPath=self.game_dir,
                style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
            if dlg.ShowModal() == wx.ID_OK:
                self.game_dir = normalise_install_folder(dlg.GetPath())
                self.folder_field.SetValue(self.game_dir)
                save_folder_choice(self.game_dir)
                self.refresh_status()
            dlg.Destroy()

        def on_action(self, _event):
            if self.working:
                return
            self.game_dir = normalise_install_folder(
                self.folder_field.GetValue())
            if not self.game_dir:
                self.status.SetLabel(
                    "Choose an install folder first, then press the button again.")
                self.choose_button.SetFocus()
                return
            save_folder_choice(self.game_dir)
            self.set_working(True)
            self.log.SetValue("")
            self.say("Working. This can take a minute on a first install.")
            threading.Thread(target=self._sync_worker, daemon=True).start()

        def _sync_worker(self):
            try:
                sync_game(self.game_dir, self.say)
            finally:
                wx.CallAfter(self._sync_done)

        def _sync_done(self):
            self.set_working(False)
            self.refresh_status()
            self.action_button.SetFocus()

        def on_close(self, _event):
            self.Close()

    def main():
        app = wx.App()
        UpdaterFrame()
        app.MainLoop()


if __name__ == "__main__":
    if wx is None:
        print("wxPython is not installed. Install it with: pip install wxPython")
    else:
        main()
