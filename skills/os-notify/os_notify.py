#!/usr/bin/env python3
"""
Cross-platform OS notification utility.
Displays native notifications on Windows, macOS, and Linux.
Falls back to stdout if no notification system is available.

Notifications are fire-and-forget: the call returns immediately after handing the
notification to the OS (it does not block for the display duration).

Exit codes: 0 = a native notification was shown; 3 = no native notifier was
available, so it only printed to stdout (callers can treat 3 as "not delivered");
1 = bad arguments.
"""

import sys
import platform
import subprocess
import argparse


def _applescript_escape(s):
    """Escape a string for embedding inside an AppleScript double-quoted literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def notify_windows(title, message, level="Info", duration_sec=8):
    """Show notification on Windows using PowerShell toast, falling back to msg."""
    # Try PowerShell toast notification first.
    ps_script = (
        f'[Windows.UI.Notifications.ToastNotificationManager, '
        f'Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; '
        f'[Windows.UI.Notifications.ToastNotification, '
        f'Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; '
        f'[Windows.Data.Xml.Dom.XmlDocument, '
        f'Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null; '
        f'$APP_ID = "python-notify"; '
        f'$template = @"'
        f'<toast><visual><binding template="ToastText02">'
        f'<text id="1">{title}</text>'
        f'<text id="2">{message}</text>'
        f'</binding></visual></toast>'
        f'"@; '
        f'$xml = New-Object Windows.Data.Xml.Dom.XmlDocument; '
        f'$xml.LoadXml($template); '
        f'$toast = New-Object Windows.UI.Notifications.ToastNotification $xml; '
        f'[Windows.UI.Notifications.ToastNotificationManager]'
        f'::CreateToastNotifier($APP_ID).Show($toast);'
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            check=True, capture_output=True, timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback to the msg command.
    try:
        subprocess.run(
            ["msg", "*", f"{title}: {message}"],
            check=True, capture_output=True, timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def notify_macos(title, message, level="Info", duration_sec=8):
    """Show notification on macOS using osascript (Notification Center)."""
    script = (
        f'display notification "{_applescript_escape(message)}" '
        f'with title "{_applescript_escape(title)}"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def notify_linux(title, message, level="Info", duration_sec=8):
    """Show notification on Linux using notify-send."""
    urgency_map = {"Warning": "normal", "Error": "critical", "Info": "low"}
    urgency = urgency_map.get(level, "low")
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-t", str(max(duration_sec, 0) * 1000),
             title, message],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def notify(title, message, level="Info", duration_sec=8):
    """
    Display an OS notification, falling back to stdout.

    Args:
        title: Notification title.
        message: Notification body text.
        level: Info, Warning, or Error (maps to urgency on Linux).
        duration_sec: Requested display duration; honored on Linux via notify-send -t,
            ignored by the native macOS/Windows mechanisms.

    Returns:
        True if a native notification was shown, False if it used the stdout fallback.
    """
    system = platform.system()
    if system == "Windows":
        if notify_windows(title, message, level, duration_sec):
            return True
    elif system == "Darwin":
        if notify_macos(title, message, level, duration_sec):
            return True
    elif system == "Linux":
        if notify_linux(title, message, level, duration_sec):
            return True

    # Fallback: print to stdout so callers never fail just because no notifier exists.
    print(f"[{level}] {title}: {message}")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Display an OS notification on Windows, macOS, or Linux"
    )
    parser.add_argument("--title", default=None, help="Notification title")
    parser.add_argument("--message", default=None, help="Notification message")
    parser.add_argument("--level", choices=["Info", "Warning", "Error"], default="Info",
                        help="Notification level (default: Info)")
    parser.add_argument("--duration", type=int, default=8,
                        help="Requested display duration in seconds (Linux only; default: 8)")
    parser.add_argument("--test", action="store_true", help="Show a test notification")
    args = parser.parse_args()

    if args.test:
        title = "OS Notification Test"
        message = "If you see this notification, os-notify is working correctly."
    else:
        title, message = args.title, args.message
        if not title or not message:
            print("Error: --title and --message are required (or use --test)", file=sys.stderr)
            sys.exit(1)

    delivered = notify(title, message, args.level, args.duration)
    # 0 = 네이티브 알림 표시, 3 = 알림 수단이 없어 stdout 폴백만 함(호출자가 "미전달"로 구분).
    sys.exit(0 if delivered else 3)


if __name__ == "__main__":
    main()
