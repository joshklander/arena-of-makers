"""Push your Arena of Makers changes to GitHub.

Double-click push_arena_changes.bat to run this. It asks what you
changed, then pushes the game files AND arena_log.txt, so Muse can
read the log straight from GitHub without you having to send the
file by hand.

Two things to know:
- This only works if this folder is a real git copy of the game. If
  you installed the game with the updater, there is no git copy here
  and the script will tell you how to get one.
- The repo is public, so the log is visible to anyone. It holds
  Windows file paths and plain game messages, but no passwords.

Nothing else is ever pushed: your .env file and temporary
files stay on your computer. There is no local save file.
"""

import datetime
import os
import subprocess
import sys

# Game files that belong on GitHub. The log is added separately below.
TRACKED_FILES = [
    "main.py",
    "game_logic.py",
    "voice_engine.py",
    "requirements.txt",
    "run_arena_of_makers.bat",
    "push_arena_changes.py",
    "push_arena_changes.bat",
    "test_game_logic.py",
    "test_main_smoke.py",
    "supabase_config.py",
    "online_save.py",
    "account.py",
    "test_key.py",
    "test_online_save.py",
    "supabase_schema.sql",
    "SOUNDS.md",
    "sounds.py",
    "build_exe.py",
    "build_exe.bat",
]

LOG_FILE = "arena_log.txt"


def say(text):
    """One plain line, so a screen reader hears it cleanly."""
    print(text)


def run_git(args):
    """Run one git command. Returns (worked, output text)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return False, "git is not installed on this computer."
    except subprocess.TimeoutExpired:
        return False, "git took too long and was stopped."
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output


def main():
    folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(folder)
    say("Arena of Makers push script.")
    say("Folder: " + folder)

    worked, output = run_git(["--version"])
    if not worked:
        say("I could not run git. " + output)
        say("Install git for Windows first, then run this again.")
        return 1

    if not os.path.isdir(os.path.join(folder, ".git")):
        say("This folder is not a git copy of the game.")
        say("The updater installs the game without git, so there is")
        say("nothing here to push from.")
        say("To get a copy you can push from, run this once:")
        say("git clone https://github.com/joshklander/arena-of-makers.git")
        say("Your fighter lives online, so there is no save file to copy.")
        return 1

    say("Pulling the newest version from GitHub first...")
    worked, output = run_git(["pull"])
    if not worked:
        say("The pull did not work, so nothing was pushed.")
        say(output)
        say("Tell Muse what it said and we will sort it out.")
        return 1
    say("Pulled the newest version.")

    message = input("What did you change? Press Enter for a plain update message: ").strip()
    if not message:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        message = "Update from Joshua (" + stamp + ")"

    to_add = [name for name in TRACKED_FILES if os.path.isfile(name)]
    log_included = False
    if os.path.isfile(LOG_FILE):
        to_add.append(LOG_FILE)
        log_included = True

    if not to_add:
        say("There are no game files here to push.")
        return 1

    worked, output = run_git(["add"] + to_add)
    if not worked:
        say("I could not stage the files. " + output)
        return 1

    worked, output = run_git(["status", "--porcelain"])
    if not worked:
        say("I could not check what changed. " + output)
        return 1
    if not output.strip():
        say("Nothing to push. No changes found, and the log is unchanged.")
        return 0

    say("Pushing: " + ", ".join(sorted(set(to_add))) + ".")
    worked, output = run_git(["commit", "-m", message])
    if not worked:
        say("I could not make the commit. " + output)
        return 1

    worked, output = run_git(["push"])
    if not worked:
        say("The push did not work. " + output)
        say("Your changes are saved here, just not on GitHub yet.")
        return 1

    say("Done. Your changes are on GitHub now.")
    if log_included:
        say("The log went with them, so Muse can read it from GitHub.")
        say("Remember the repo is public, so anyone can see the log.")
    say("Your .env file was not pushed. It stays on this computer.")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        say("Stopped. Nothing was pushed.")
        code = 1
    input("Press Enter to close.")
    sys.exit(code)
