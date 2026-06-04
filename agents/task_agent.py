import importlib, subprocess, json
from agents.base_agent import BaseAgent

IS_TRX = "TERMUX_VERSION" in __import__("os").environ or __import__("os").path.exists("/data/data/com.termux")

class TaskAgent(BaseAgent):
    name = "TaskAgent"
    description = "Controls apps, device settings, system operations, and file management"

    TASK_MAP = {
        "open play store": ("open_app", "play store"),
        "open prime video": ("open_app", "prime video"),
        "open youtube": ("open_app", "youtube"),
        "open chrome": ("open_app", "chrome"),
        "open telegram": ("open_app", "telegram"),
        "open whatsapp": ("open_app", "whatsapp"),
        "open spotify": ("open_app", "spotify"),
        "open instagram": ("open_app", "instagram"),
        "open facebook": ("open_app", "facebook"),
        "open twitter": ("open_app", "twitter"),
        "open linkedin": ("open_app", "linkedin"),
        "open netflix": ("open_app", "netflix"),
        "open calculator": ("open_app", "calculator"),
        "open maps": ("open_app", "maps"),
        "open gmail": ("open_app", "gmail"),
        "open clock": ("open_app", "clock"),
        "open contacts": ("open_app", "contacts"),
        "open settings": ("open_app", "settings"),
        "open phone": ("open_app", "phone"),
        "open gallery": ("open_gallery", False),
        "open camera": ("take_photo", False),
        "open files": ("access_storage", False),
        "open storage": ("access_storage", False),
        "open": ("open_app", True),
        "launch": ("open_app", True),
        "force stop": ("close_app", True),
        "kill": ("close_app", True),
        "close": ("close_app", True),
        "quit": ("close_app", True),
        "play on youtube": ("play_yt", True),
        "search youtube": ("play_yt", True),
        "youtube search": ("play_yt", True),
        "play music": ("play_yt", True),
        "play song": ("play_yt", True),
        "play video": ("play_yt", True),
        "play": ("play_yt", True),
        "website": ("open_website", True),
        "browse": ("open_website", True),
        "url": ("open_website", True),
        "search google": ("search", True),
        "google search": ("search", True),
        "increase volume": ("control_volume", "up"),
        "decrease volume": ("control_volume", "down"),
        "volume up": ("control_volume", "up"),
        "volume down": ("control_volume", "down"),
        "turn up volume": ("control_volume", "up"),
        "turn down volume": ("control_volume", "down"),
        "turn up": ("control_volume", "up"),
        "turn down": ("control_volume", "down"),
        "mute": ("control_volume", "mute"),
        "increase brightness": ("control_brightness", "up"),
        "decrease brightness": ("control_brightness", "down"),
        "brightness up": ("control_brightness", "up"),
        "brightness down": ("control_brightness", "down"),
        "brighten": ("control_brightness", "up"),
        "dim screen": ("control_brightness", "down"),
        "turn on wifi": ("toggle_wifi", "on"),
        "turn off wifi": ("toggle_wifi", "off"),
        "enable wifi": ("toggle_wifi", "on"),
        "disable wifi": ("toggle_wifi", "off"),
        "wifi on": ("toggle_wifi", "on"),
        "wifi off": ("toggle_wifi", "off"),
        "turn on bluetooth": ("toggle_bluetooth", "on"),
        "turn off bluetooth": ("toggle_bluetooth", "off"),
        "enable bluetooth": ("toggle_bluetooth", "on"),
        "disable bluetooth": ("toggle_bluetooth", "off"),
        "bluetooth on": ("toggle_bluetooth", "on"),
        "bluetooth off": ("toggle_bluetooth", "off"),
        "turn on": ("_toggle_dispatch", True),
        "turn off": ("_toggle_dispatch", True),
        "switch on": ("_toggle_dispatch", True),
        "switch off": ("_toggle_dispatch", True),
        "screenshot": ("take_shot", False),
        "take photo": ("take_photo", False),
        "take a photo": ("take_photo", False),
        "next song": ("media_control", "next"),
        "previous song": ("media_control", "previous"),
        "next track": ("media_control", "next"),
        "previous track": ("media_control", "previous"),
        "send sms": ("send_sms", True),
        "send message": ("send_sms", True),
        "send msg": ("send_whatsapp", True),
        "read sms": ("read_sms", False),
        "check sms": ("read_sms", False),
        "inbox": ("read_sms", False),
        "my messages": ("read_sms", False),
        "contacts": ("get_contacts", False),
        "my contacts": ("get_contacts", False),
        "show contacts": ("get_contacts", False),
        "call log": ("get_call_log", False),
        "recent calls": ("get_call_log", False),
        "share": ("share_content", True),
        "share this": ("share_content", True),
        "wifi info": ("get_wifi_info", False),
        "wifi connection": ("get_wifi_info", False),
        "my wifi": ("get_wifi_info", False),
        "set wallpaper": ("set_wallpaper", True),
        "change wallpaper": ("set_wallpaper", True),
        "shutdown": ("shutdown", False),
        "restart": ("restart", False),
        "lock": ("lock_screen", False),
        "lock screen": ("lock_screen", False),
        "screen lock": ("lock_screen", False),
        "what time": ("get_time", False),
        "current time": ("get_time", False),
        "check time": ("get_time", False),
        "battery level": ("get_battery_status", False),
        "check battery": ("get_battery_status", False),
        "system info": ("get_system_info", False),
        "news": ("get_news", False),
        "notification": ("read_notifications", False),
        "notifications": ("read_notifications", False),
        "check notifications": ("read_notifications", False),
        "read notifications": ("read_notifications", False),
        "messages": ("read_notifications", False),
        "call": ("call_contact", True),
        "make a call": ("call_contact", True),
        "ring": ("call_contact", True),
        "note": ("write_note", True),
        "remind": ("write_note", True),
        "write note": ("write_note", True),
        "make a note": ("write_note", True),
        "my location": ("get_location", False),
        "where am i": ("get_location", False),
        "whatsapp": ("open_app", "whatsapp"),
        "send whatsapp": ("send_whatsapp", True),
        "message on whatsapp": ("send_whatsapp", True),
        "msg on whatsapp": ("send_whatsapp", True),
        "send a message": ("send_whatsapp", True),
        "send a msg": ("send_whatsapp", True),
        "youtube": ("open_app", "youtube"),
    }

    VALID_FUNCTIONS = ["open_app", "close_app", "play_yt", "open_website", "search", "control_volume",
        "control_brightness", "toggle_wifi", "toggle_bluetooth", "take_shot", "take_photo", "open_gallery",
        "access_storage", "write_note", "get_battery_status", "get_system_info", "get_news", "call_contact",
        "read_notifications", "get_realtime_data", "get_time", "lock_screen", "shutdown", "restart",
        "cancel_shutdown", "send_sms", "read_sms", "get_contacts", "media_control", "share_content",
        "get_wifi_info", "set_wallpaper", "get_call_log", "get_location", "send_whatsapp"]

    def run(self, query: str, parameters: dict = None) -> dict:
        parameters = parameters or {}
        q = query.lower().strip()

        compound_parts = [s.strip() for s in q.split(" and ") if s.strip()]
        compound_targets = [s.strip() for s in query.split(" and ") if s.strip()]

        if len(compound_parts) > 1:
            results = []
            for i in range(len(compound_parts)):
                r = self._process_single(compound_targets[i], parameters)
                results.append(r)
            return self._merge_compound_results(results)

        return self._process_single(query, parameters)

    def _process_single(self, query: str, parameters: dict) -> dict:
        q = query.lower().strip()

        matched_fn = None
        matched_target = query
        for kw in sorted(self.TASK_MAP, key=len, reverse=True):
            if kw in q:
                fn_name, needs_target_or_value = self.TASK_MAP[kw]
                matched_fn = fn_name
                if isinstance(needs_target_or_value, str):
                    matched_target = needs_target_or_value
                elif needs_target_or_value:
                    idx = q.find(kw)
                    matched_target = query[idx + len(kw):].strip()
                    if not matched_target:
                        matched_target = parameters.get("target", query)
                break
        if not matched_fn:
            parsed = self._ask_json([{"role": "user", "content": f"Map this to a task function: {query}"}],
                system="Return JSON with keys: function and target. Functions: open_app, close_app, play_yt, search, take_shot, get_time, lock_screen, shutdown, restart, write_note, get_battery_status, get_system_info, get_news, control_volume, control_brightness, toggle_wifi, toggle_bluetooth, open_website, open_gallery, access_storage, take_photo, call_contact, read_notifications, get_realtime_data, send_sms, read_sms, get_contacts, get_call_log, media_control, share_content, get_wifi_info, set_wallpaper, get_location. target: string or null")
            matched_fn = parsed.get("function", "get_time")
            matched_target = parsed.get("target") or query
        if matched_fn == "_toggle_dispatch":
            is_on = any(kw in q for kw in ["turn on", "switch on"])
            device = (matched_target or "").lower().strip()
            if not device:
                return self._err("Turn on/off what?")
            if "wifi" in device or "wlan" in device:
                matched_fn, matched_target = "toggle_wifi", ("on" if is_on else "off")
            elif "bluetooth" in device or "bt" in device:
                matched_fn, matched_target = "toggle_bluetooth", ("on" if is_on else "off")
            elif "flash" in device or "torch" in device or "light" in device:
                if IS_TRX:
                    subprocess.run(["termux-torch", "on" if is_on else "off"], capture_output=True, timeout=5)
                return self._ok(f"{'Flashlight on' if is_on else 'Flashlight off'}.")
            else:
                return self._err(f"Can't toggle '{device}' — try wifi or bluetooth.")
        return self._execute(matched_fn, matched_target, parameters)

    def _merge_compound_results(self, results: list) -> dict:
        texts = []
        all_ok = True
        compound_exec = []
        for r in results:
            txt = str(r.get("result", ""))
            if txt:
                texts.append(txt)
            if not r.get("success"):
                all_ok = False
            meta = r.get("metadata", {})
            if meta.get("task"):
                compound_exec.append({
                    "task": meta["task"],
                    "target": meta.get("target", "")
                })
        combined_text = ". ".join(texts) if texts else "Actions completed."
        return {
            "result": combined_text,
            "success": all_ok,
            "metadata": {
                "compound_execution": compound_exec,
                "tasks": [m.get("task") for m in compound_exec],
                "targets": [m.get("target") for m in compound_exec],
            }
        }

    def _execute(self, fn_name: str, target: str, parameters: dict) -> dict:
        try:
            tasks = importlib.import_module("skills.tasks")
            fn = getattr(tasks, fn_name, None)
            if not fn:
                return self._err(f"Task '{fn_name}' not found.")
            import inspect
            sig = inspect.signature(fn)
            if len(sig.parameters) == 0:
                result = fn()
            else:
                result = fn(target)
            return self._ok(str(result), metadata={"task": fn_name, "target": target})
        except Exception as e:
            return self._err(f"Task execution error: {e}")
