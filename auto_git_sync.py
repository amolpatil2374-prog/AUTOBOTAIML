import os
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
WATCH_FOLDER = os.path.join(PROJECT_DIR, "setup")

WAIT_SECONDS = 60

# ============================================================
# GIT FUNCTION
# ============================================================

def git_sync():

    print("\n========================================")
    print("Changes detected - syncing with GitHub")
    print("========================================")

    try:
        # Check status
        subprocess.run(
            ["git", "status", "--short"],
            cwd=PROJECT_DIR,
            check=True
        )

        # Add only setup folder
        subprocess.run(
            ["git", "add", "setup/"],
            cwd=PROJECT_DIR,
            check=True
        )

        # Check if anything is staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=PROJECT_DIR
        )

        # Return code 0 = no changes
        if result.returncode == 0:
            print("No changes to commit.")
            return

        # Commit
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        subprocess.run(
            ["git", "commit", "-m", f"Auto update setup - {timestamp}"],
            cwd=PROJECT_DIR,
            check=True
        )

        # Push
        subprocess.run(
            ["git", "push"],
            cwd=PROJECT_DIR,
            check=True
        )

        print("\nSUCCESS: Changes pushed to GitHub.")

    except subprocess.CalledProcessError as e:
        print("\nGit sync failed.")
        print("Error:", e)


# ============================================================
# FILE WATCHER
# ============================================================

class ChangeHandler(FileSystemEventHandler):

    def __init__(self):
        self.last_change = 0

    def on_any_event(self, event):

        if event.is_directory:
            return

        # Ignore temporary files
        filename = os.path.basename(event.src_path)

        if filename.startswith("~"):
            return

        if filename.endswith(".tmp"):
            return

        self.last_change = time.time()

        print(f"\nChange detected: {event.src_path}")


# ============================================================
# MAIN
# ============================================================

if not os.path.exists(WATCH_FOLDER):
    print(f"ERROR: Folder not found:")
    print(WATCH_FOLDER)
    input("\nPress Enter to exit...")
    exit()

print("========================================")
print("       GITHUB AUTO SYNC")
print("========================================")
print(f"Project : {PROJECT_DIR}")
print(f"Watching: {WATCH_FOLDER}")
print(f"Wait    : {WAIT_SECONDS} seconds")
print("----------------------------------------")
print("Edit files normally.")
print("Changes will automatically be pushed.")
print("Press CTRL+C to stop.")
print("========================================")

event_handler = ChangeHandler()

observer = Observer()
observer.schedule(
    event_handler,
    WATCH_FOLDER,
    recursive=True
)

observer.start()

try:

    while True:

        time.sleep(5)

        if event_handler.last_change > 0:

            elapsed = time.time() - event_handler.last_change

            if elapsed >= WAIT_SECONDS:

                event_handler.last_change = 0

                git_sync()

except KeyboardInterrupt:

    print("\nStopping GitHub auto sync...")

    observer.stop()

observer.join()