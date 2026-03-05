# TalkType: Local Voice-to-Text for Mecris

> **Mecris Strategic Tool**  
> *High-performance local transcription using OpenAI Whisper*

TalkType is a local transcription service that allows you to "talk-type" directly into any application. It consists of a Whisper API server (running locally) and a client that listens for a hotkey (F9) to record and transcribe audio.

## 🚀 Quick Start

```bash
# 1. Setup the environment and dependencies
make setup

# 2. Start the Whisper server (downloads model on first run)
make server

# 3. Run the TalkType client
make client
```

**Usage**: Place your cursor in any text field, press **F9** to start recording, speak, and press **F9** again to transcribe.

### ⌨️ Hotkeys
- **F9**: Start/Stop recording.
- **F8**: **Recovery** - Re-paste the last successful transcription.
- **F7**: **Retry** - Re-transcribe the last audio recording (useful if API timed out).

## 📋 Prerequisites

- **`uv`**: Fast Python package manager.
- **`ffmpeg`**: Required for audio processing.
- **Python 3.10+**: Managed via `uv`.
- **macOS Permissions**: Terminal/IDE requires **Accessibility** and **Microphone** permissions.

## 🔧 Management Commands

- `make setup`: Initializes the virtual environment and installs requirements.
- `make server`: Starts the background Whisper server.
- `make client`: Runs the interactive hotkey client (use `make client ARGS="--setup"` for first-time config).
- `make status`: Checks if the server is healthy and responding.
- `make logs`: Tails the server output logs.
- `make stop-server`: Gracefully kills the background server.
- `make sync-upstream`: Syncs the `talktype-repo` with the latest upstream changes.
- `make clean`: Removes PID files and log files.

## ⚙️ Configuration

You can override the default Whisper settings by passing variables to `make server`:

```bash
# Use a larger model and auto-detect best device (CUDA or CPU)
make server WHISPER_MODEL=large-v3 WHISPER_DEVICE=auto
```

- **Models**: `tiny`, `base`, `small`, `medium` (default), `large-v3`, `turbo`.
- **Devices**: `auto` (recommended), `cpu`, `cuda`.
- **Note on macOS**: `mps` (Metal Performance Shaders) is not currently supported by the underlying `faster-whisper` implementation. Use `cpu` or `auto`.

## 🛠️ Troubleshooting

### macOS Accessibility
TalkType requires Accessibility permissions to inject keystrokes.
1. Go to **System Settings > Privacy & Security > Accessibility**.
2. Ensure your Terminal (e.g., iTerm2, Terminal.app) or IDE is enabled.

### Microphone Access
Ensure your terminal has permission to access the microphone.

### Port Conflicts
The server defaults to port `8002`. If this is occupied:
```bash
make server WHISPER_PORT=9000
make client WHISPER_PORT=9000
```

---
*Sources derived from [kingdonb/talktype](https://github.com/kingdonb/talktype)*
