# TalkType: Architecture & Troubleshooting Guide

TalkType is a remarkably lean, high-performance voice-to-text service. It achieves near-instant transcription and pasting across the entire operating system without relying on a heavy GUI framework (like Electron, Qt, or Tauri).

This document serves as the repository of knowledge for how TalkType achieves its minimal footprint and how to troubleshoot its edge cases.

## 🧠 Architectural Footprint

TalkType relies on four minimal pillars to achieve system-wide voice typing:

1. **Global Hotkey Listening (`pynput`)**:
   Instead of running an active GUI window to capture keyboard events, TalkType uses `pynput.keyboard.Listener`. This binds directly to the OS accessibility APIs (like macOS Accessibility or X11/Wayland input handlers) to intercept keystrokes (e.g., `F9`) globally, in the background.

2. **In-Memory Audio Capture (`sounddevice` + `numpy`)**:
   When you press record, `sounddevice` opens a non-blocking audio stream directly from your microphone. It continuously appends audio frames into a lightweight `numpy` array. There is **zero disk I/O** during recording—it all happens in RAM, which is why it's so fast.

3. **Transcription Routing (Local or Cloud)**:
   Once recording stops, the `numpy` array is sent either:
   - **Locally**: To the background `whisper_server.py` running `faster-whisper` (CTranslate2 bindings), which is highly optimized for CPU/GPU.
   - **Cloud (Groq)**: Bypassing local compute entirely, the audio buffer is compressed in-memory and sent to Groq's wildly fast Whisper API.

4. **Simulated Keystroke Injection (`pyautogui` / `xdotool` / `osascript`)**:
   TalkType does not type out words letter-by-letter (which is slow and prone to race conditions). Instead, it:
   1. Saves your current clipboard.
   2. Replaces your clipboard with the transcribed text.
   3. Sends a raw OS-level "Paste" command (`Cmd+V` or `Ctrl+V`).
   4. Restores your old clipboard in the background after a slight delay.

---

## ⚙️ The "System Service" Mode Update

Recently, TalkType received an upstream update (likely pulled via `make sync-upstream`), which introduced `setup_wizard.py`. 

This setup wizard includes an **"Install as a System Service"** feature for Linux users. It generates a `.service` file and registers TalkType with `systemd --user`. This allows the Whisper server to automatically start in the background when the user logs in, completely eliminating the need to manually run `make server` in a terminal window.

*(Note: On macOS, this equivalent feature would use `launchd` via `plist` files, but currently, the background server is typically managed via `nohup` in the Makefile).*

---

## 🛠️ Bug Post-Mortem: The "Bye^C" Hang

### The Symptoms
- The user pressed `F9` to record, spoke, and pressed `F9` again to stop.
- The transcription succeeded (the text was saved to `~/.cache/talktype/history.jsonl`).
- The user attempted to terminate the client in the terminal with `Ctrl+C`.
- The terminal printed `Bye^C` but the process remained entirely frozen and refused to exit.

### The Root Causes

We identified two critical race conditions responsible for this unresponsiveness:

#### 1. The AppleScript Blocking Trap (`osascript`)
On macOS, TalkType tries to track the currently focused window using `subprocess.check_output(["osascript", "-e", script])` so it knows where to return focus after pasting.
If the OS Window Manager is busy, or if AppleScript encounters a permission prompt in the background, `subprocess` will block *indefinitely*. 
**The Fix**: We injected a strict `timeout=1.0` into the `subprocess` calls. If the OS takes longer than 1 second to identify the active window, TalkType gracefully fails the focus attempt rather than freezing the entire application.

#### 2. The Python `sys.exit()` Thread Trap
When you pressed `Ctrl+C`, the `signal_handler` caught the `SIGINT` signal, printed `Bye!`, and called `sys.exit(0)`.
In Python, `sys.exit()` simply raises a `SystemExit` exception in the main thread. However, TalkType runs several non-daemon background threads (like the `pynput` keyboard listener and the `sounddevice` audio stream). Because those threads were still technically "alive" (perhaps waiting for a slow UI paste operation), Python refused to terminate the process, leaving you stuck in zombie limbo.
**The Fix**: We replaced `sys.exit(0)` with `os._exit(0)` in the `talktype.py` signal handler. Unlike `sys.exit()`, `os._exit()` forces the operating system to brutally terminate the process and all its threads immediately, guaranteeing a clean exit on `Ctrl+C`.
