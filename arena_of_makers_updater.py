"""Arena of Makers updater - install the game or pull the latest version.

Accessible wxPython window, built for screen reader users (NVDA / VoiceOver):
every action is a native focusable button and every result is plain text.

How it works
------------
- You pick an install folder. If the game is not there yet, the updater
  downloads the whole game from GitHub and installs it.
- If the game is already there, it asks GitHub for the newest version and
  downloads only the files that changed.
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
"""

import base64
import hashlib
import json
import os
import shutil
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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FOLDER_STATE_FILE = os.path.join(SCRIPT_DIR, "arena_updater_state.json")
VERSION_FILE_NAME = "arena_version.json"

# Files the updater itself uses. They are never written by a sync, even if
# a future version of the repository ever listed them, because overwriting
# the program while it is running could break it.
PROTECTED_FILES = {
    "arena_of_makers_updater.py",
    "run_arena_of_makers_updater.bat",
    "arena_updater_state.json",
    VERSION_FILE_NAME,
}


def default_install_folder():
    """Where the game goes unless the user picks somewhere else."""
    return os.path.join(SCRIPT_DIR, "Arena of Makers")


def load_folder_choice():
    """Return the install folder the user picked before, or the default."""
    try:
        with open(FOLDER_STATE_FILE, "r", encoding="utf-8") as f:
            folder = json.load(f).get("install_folder")
        if folder:
            return folder
    except (OSError, ValueError, AttributeError):
        pass
    return default_install_folder()


def save_folder_choice(folder):
    try:
        with open(FOLDER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"install_folder": folder}, f)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# GitHub API helpers (plain urllib, no extra packages, no token needed)
# --------------------------------------------------------------------------

def api_get(path):
    """GET one public API path. Returns (status, payload dict or list).

    Status 403 usually means GitHub's free limit for unsigned-in requests
    was reached. Status 404 means the thing asked for is not there.
    """
    url = API_BASE + path
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "ArenaOfMakersUpdater")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            payload = {"message": "GitHub answered with an error."}
        return e.code, payload
    except Exception as e:
        return 0, {"message": "Could not reach GitHub: %s" % e}


def get_head_sha():
    """Return the newest commit id on main, or None when it cannot be read."""
    status, payload = api_get("/git/refs/heads/main")
    if status == 200:
        return payload.get("object", {}).get("sha")
    return None


def get_tree():
    """Return the full file list of main, or None when it cannot be read.

    Each entry has path, sha (the git blob id) and size.
    """
    status, payload = api_get("/git/trees/main?recursive=1")
    if status == 200 and isinstance(payload, dict):
        return [t for t in payload.get("tree", []) if t.get("type") == "blob"]
    return None


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


def is_installed(game_dir):
    """True when this folder already has a game installed by this updater."""
    return os.path.exists(version_path(game_dir))


def plan_sync(tree, game_dir):
    """Compare the repository file list with the local folder.

    Returns (to_download, left_in_place, synced_files). to_download is a
    list of tree entries that are missing or different locally.
    left_in_place is a list of files that were synced before but are no
    longer in the repository; they are never deleted, only reported.
    synced_files is the full set of files the sync will leave in place.
    """
    _head, previous_files = load_state(game_dir)
    to_download = []
    synced_files = set()
    for entry in tree:
        path = entry["path"]
        if path in PROTECTED_FILES:
            continue
        synced_files.add(path)
        local = os.path.join(game_dir, path)
        if local_blob_hash(local) != entry["sha"]:
            to_download.append(entry)
    left_in_place = []
    for path in sorted(previous_files):
        if path in PROTECTED_FILES:
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


def install_from_zip(zip_path, game_dir, log):
    """Unpack a GitHub zipball into the game folder. Returns (ok, message).

    Files are copied over one by one. Nothing already in the folder is
    ever removed, so saves, settings and any other local-only files
    survive an install untouched.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            if not names:
                return False, "The downloaded game file was empty."
            top = names[0].split("/")[0]
            if zf.testzip() is not None:
                return False, "The downloaded game file was damaged."
            tmpdir = tempfile.mkdtemp(prefix="arena-makers-install-")
            try:
                zf.extractall(tmpdir)
                src = os.path.join(tmpdir, top)
                for root, _dirs, files in os.walk(src):
                    for name in files:
                        s = os.path.join(root, name)
                        rel = os.path.relpath(s, src)
                        if rel.replace(os.sep, "/") in PROTECTED_FILES:
                            continue
                        d = os.path.join(game_dir, rel)
                        os.makedirs(os.path.dirname(d), exist_ok=True)
                        shutil.copy2(s, d)
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
        return True, ""
    except Exception as e:
        return False, "Could not unpack the game: %s" % e


def sync_game(game_dir, log):
    """Install the game or bring it up to date. Runs in a worker thread.

    log(text) is called with plain-word progress lines. Returns True when
    the local game now matches GitHub, False otherwise.
    """
    game_dir = os.path.abspath(game_dir)
    installed = is_installed(game_dir)
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
            ok, message = install_from_zip(tmp, game_dir, log)
            if not ok:
                log(message)
                return False
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        tree = get_tree()
        if tree is not None:
            save_state(game_dir, head,
                       {e["path"] for e in tree if e["path"] not in PROTECTED_FILES})
        log("Arena of Makers is installed. You can play it now.")
        return True

    stored_head, _files = load_state(game_dir)
    if stored_head != head:
        log("A newer version is on GitHub. Checking which files changed.")
    tree = get_tree()
    if tree is None:
        log("Could not read the file list from GitHub. Try again later.")
        return False
    to_download, left_in_place, synced_files = plan_sync(tree, game_dir)
    if not to_download:
        save_state(game_dir, head, synced_files)
        for path in left_in_place:
            log("%s is no longer in the game, but your copy was left in place." % path)
        log("You already have the newest version. Nothing to download.")
        return True
    if stored_head == head:
        log("Some game files were missing or different. Downloading %d files."
            % len(to_download))
    else:
        log("Downloading %d changed files." % len(to_download))
    for i, entry in enumerate(to_download, 1):
        dest = os.path.join(game_dir, entry["path"])
        ok, message = download_file(
            entry["path"], entry["sha"], entry.get("size"), dest)
        if not ok:
            log(message)
            return False
        if i % 10 == 0 or i == len(to_download):
            log("Downloaded %d of %d files." % (i, len(to_download)))
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
            if is_installed(self.game_dir):
                _head, files = load_state(self.game_dir)
                self.status.SetLabel(
                    "Arena of Makers is installed in this folder "
                    "(%d files)." % len(files))
                self.action_button.SetLabel("Check for updates")
            else:
                self.status.SetLabel(
                    "Arena of Makers is not installed in this folder yet.")
                self.action_button.SetLabel("Install Arena of Makers")

        def say(self, text):
            wx.CallAfter(self.log.AppendText, text + "\n")

        def set_working(self, working):
            self.working = working
            self.action_button.Enable(not working)
            self.choose_button.Enable(not working)
            self.folder_field.Enable(not working)

        def on_folder_typed(self, _event):
            self.game_dir = self.folder_field.GetValue().strip()
            save_folder_choice(self.game_dir)
            self.refresh_status()

        def on_choose_folder(self, _event):
            dlg = wx.DirDialog(
                self, "Choose where to install Arena of Makers",
                defaultPath=self.game_dir,
                style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
            if dlg.ShowModal() == wx.ID_OK:
                self.game_dir = dlg.GetPath()
                self.folder_field.SetValue(self.game_dir)
                save_folder_choice(self.game_dir)
                self.refresh_status()
            dlg.Destroy()

        def on_action(self, _event):
            if self.working:
                return
            self.game_dir = self.folder_field.GetValue().strip()
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
