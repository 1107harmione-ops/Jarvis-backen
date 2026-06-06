"""Open App tool - Launch Android apps via ADB."""

import subprocess
import json

TOOL_NAME = "open_app"
TOOL_DESCRIPTION = "Open/launch an Android app by package name using ADB"
TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "package_name": {
            "type": "string",
            "description": "Android package name to launch (e.g. com.android.chrome)"
        },
        "activity": {
            "type": "string",
            "description": "Optional specific activity to launch"
        }
    },
    "required": ["package_name"]
}


def register(registry):
    """Register this tool with the registry."""
    registry.register(TOOL_NAME, handle, TOOL_DESCRIPTION, TOOL_PARAMETERS)


def handle(package_name: str, activity: str = None) -> dict:
    """Launch an Android app via ADB monkey or am start."""
    try:
        if activity:
            cmd = f"adb shell am start -n {package_name}/{activity}"
        else:
            # Use monkey for reliable launch without knowing activity
            cmd = f"adb shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            # Try am start as fallback
            fallback = f"adb shell am start -n {package_name}/.MainActivity"
            result = subprocess.run(
                fallback, shell=True, capture_output=True, text=True, timeout=15
            )
        return {
            "success": result.returncode == 0,
            "output": result.stdout or result.stderr,
            "package": package_name,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "ADB command timed out", "package": package_name}
    except FileNotFoundError:
        return {"success": False, "error": "ADB not found. Is Android SDK installed?", "package": package_name}
    except Exception as e:
        return {"success": False, "error": str(e), "package": package_name}
