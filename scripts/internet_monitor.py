#!/usr/bin/env python3

import csv
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

# ==========================================================
# CONFIGURATION
# ==========================================================

# Change this to your local GitHub repository directory.
REPO_DIR = Path(__file__).resolve().parent.parent
HISTORY_FILE = REPO_DIR / "internet_history.csv"

# Check connectivity every 30 seconds.
CHECK_INTERVAL = 30

# Connection test timeout, in seconds.
CONNECTION_TIMEOUT = 3

# Independent internet connectivity test endpoints.
TEST_ENDPOINTS = [
    ("1.1.1.1", 443),
    ("8.8.8.8", 443),
]

# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def current_time():
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )


def internet_available():
    """
    Return True if at least one external endpoint
    accepts a TCP connection.
    """
    for host, port in TEST_ENDPOINTS:
        try:
            with socket.create_connection(
                (host, port),
                timeout=CONNECTION_TIMEOUT
            ):
                return True
        except OSError:
            continue

    return False


def initialize_history():
    """Create the CSV file if it does not exist."""
    if not HISTORY_FILE.exists():
        with open(HISTORY_FILE, "w", newline="") as file:
            writer = csv.writer(file)

            writer.writerow([
                "timestamp_utc",
                "event",
                "outage_duration_seconds"
            ])


def record_event(event, outage_duration=None):
    """Append an event to the local CSV history."""
    timestamp = current_time()

    with open(HISTORY_FILE, "a", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            timestamp,
            event,
            outage_duration if outage_duration is not None else ""
        ])

    print(
        f"[{timestamp}] {event}"
        + (
            f" | Outage duration: {outage_duration} seconds"
            if outage_duration is not None
            else ""
        ),
        flush=True
    )


def git_command(*args):
    """Run a Git command inside the repository."""
    return subprocess.run(
        ["git", *args],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        timeout=30
    )


def push_history():
    """
    Commit the history file if it changed and push
    committed changes to the configured Git branch.
    """
    try:
        # Stage only the monitoring history.
        result = git_command(
            "add", "--", HISTORY_FILE.name
        )

        if result.returncode != 0:
            print("Git add failed:", result.stderr, flush=True)
            return False

        # Check whether the staged history has changed.
        result = git_command(
            "diff", "--cached", "--quiet", "--",
            HISTORY_FILE.name
        )

        if result.returncode == 0:
            # Nothing new to commit.
            return True

        if result.returncode != 1:
            print("Git diff failed:", result.stderr, flush=True)
            return False

        # Commit the updated history.
        result = git_command(
            "commit", "-m", "Update Raspberry Pi internet history"
        )

        if result.returncode != 0:
            print("Git commit failed:", result.stderr, flush=True)
            return False

        # Push the commit to the configured upstream branch.
        result = git_command("push")

        if result.returncode != 0:
            print("Git push failed:", result.stderr, flush=True)
            return False

        print("History successfully pushed to GitHub.", flush=True)
        return True

    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Git operation failed: {error}", flush=True)
        return False


# ==========================================================
# MAIN MONITOR
# ==========================================================

def main():
    if not REPO_DIR.is_dir():
        raise RuntimeError(
            f"Repository directory does not exist: {REPO_DIR}"
        )

    if not (REPO_DIR / ".git").is_dir():
        raise RuntimeError(
            f"Not a Git repository: {REPO_DIR}"
        )

    initialize_history()

    previous_status = None
    disconnected_at = None

    print("Raspberry Pi internet monitor started.", flush=True)
    print(f"Repository: {REPO_DIR}", flush=True)
    print(f"Check interval: {CHECK_INTERVAL} seconds", flush=True)

    while True:
        try:
            online = internet_available()
            status = "CONNECTED" if online else "DISCONNECTED"

            # Record only status changes.
            if status != previous_status:

                if status == "DISCONNECTED":
                    disconnected_at = datetime.now(timezone.utc)
                    record_event("DISCONNECTED")

                else:
                    outage_duration = None

                    if disconnected_at is not None:
                        outage_duration = int(
                            (
                                datetime.now(timezone.utc)
                                - disconnected_at
                            ).total_seconds()
                        )

                    record_event(
                        "CONNECTED",
                        outage_duration
                    )

                    disconnected_at = None

                previous_status = status

            # Push pending history whenever internet is available.
            # This also retries earlier failed Git pushes.
            if online:
                push_history()

            time.sleep(CHECK_INTERVAL)

        except Exception as error:
            print(f"Monitor error: {error}", flush=True)
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
