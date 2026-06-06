"""Device Actions tool - Control Android device settings and features via ADB."""

import subprocess
import json

TOOL_NAME = "device_actions"
TOOL_DESCRIPTION = "Control Android device: volume, screenshot, wifi, bluetooth, flashlight, clipboard, orientation"
TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "volume_up", "volume_down", "mute",
                "screenshot", "wifi_on", "wifi_off",
                "bluetooth_on", "bluetooth_off",
                "flashlight_on", "flashlight_off",
                "set_clipboard", "orientation_portrait", "orientation_landscape",
                "lock_screen", "unlock_screen",
                "press_home", "press_back", "press_recent",
            ],
            "description": "The device action to perform"
        },
        "value": {
            "type": "string",
            "description": "Optional value (e.g. text for set_clipboard)"
        }
    },
    "required": ["action"]
}


def _run_adb(cmd: str, timeout: int = 10) -> dict:
    """Run an ADB command safely."""
    try:
        full_cmd = f"adb shell {cmd}"
        result = subprocess.run(
            full_cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip() or result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "ADB command timed out"}
    except FileNotFoundError:
        return {"success": False, "error": "ADB not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def register(registry):
    """Register this tool with the registry."""
    registry.register(TOOL_NAME, handle, TOOL_DESCRIPTION, TOOL_PARAMETERS)


def handle(action: str, value: str = None) -> dict:
    """Execute a device action via ADB."""

    adb_commands = {
        "volume_up": "input keyevent 24",
        "volume_down": "input keyevent 25",
        "mute": "input keyevent 164",
        "screenshot": f"screencap -p /sdcard/screenshot.png && echo 'Screenshot saved'",
        "wifi_on": "svc wifi enable",
        "wifi_off": "svc wifi disable",
        "bluetooth_on": "svc bluetooth enable",
        "bluetooth_off": "svc bluetooth disable",
        "flashlight_on": "cmd flashlight set_flashlight true 2>/dev/null || echo 'Flashlight not supported'",
        "flashlight_off": "cmd flashlight set_flashlight false 2>/dev/null || echo 'Flashlight not supported'",
        "orientation_portrait": "settings put system user_rotation 0",
        "orientation_landscape": "settings put system user_rotation 1",
        "lock_screen": "input keyevent 26",
        "unlock_screen": "input keyevent 82",
        "press_home": "input keyevent 3",
        "press_back": "input keyevent 4",
        "press_recent": "input keyevent 187",
    }

    if action == "set_clipboard":
        if not value:
            return {"success": False, "error": "value required for set_clipboard"}
        return _run_adb(
            f'am broadcast -a clipper.set --es text "{value.replace(chr(34), chr(92) + chr(34))}" '
            f'2>/dev/null || echo "Clipboard broadcast not available"'
        )

    if action not in adb_commands:
        return {"success": False, "error": f"Unknown action: {action}"}

    result = _run_adb(adb_commands[action])

    # If screenshot, also pull to a temp location
    if action == "screenshot" and result["success"]:
        pull_result = subprocess.run(
            "adb pull /sdcard/screenshot.png /tmp/jarvis_screenshot.png 2>/dev/null && echo 'Pulled' || echo 'Pull failed'",
            shell=True, capture_output=True, text=True, timeout=10
        )
        result["screenshot_path"] = "/tmp/jarvis_screenshot.png" if "Pulled" in pull_result.stdout else None

    return result
