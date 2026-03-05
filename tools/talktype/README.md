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

## 📋 Prerequisites

- **`uv`**: Fast Python package manager.
- **`ffmpeg`**: Required for audio processing.
- **Python 3.10+**: Managed via `uv`.
- **macOS Permissions**: Terminal/IDE requires **Accessibility** and **Microphone** permissions.

## 🔧 Management Commands

- `make setup`: Initializes the virtual environment and installs requirements.
- `make server`: Starts the background Whisper server.
- `make client`: Runs the interactive hotkey client.
- `make status`: Checks if the server is healthy and responding.
- `make logs`: Tails the server output logs.
- `make stop-server`: Gracefully kills the background server.
- `make clean`: Removes PID files and log files.

## ⚙️ Configuration

You can override the default Whisper settings by passing variables to `make server`:

```bash
# Use a larger model and the Mac GPU (MPS)
make server WHISPER_MODEL=medium WHISPER_DEVICE=mps
```

- **Models**: `tiny`, `base`, `small` (default), `medium`, `large-v3`, `turbo`.
- **Devices**: `cpu` (default), `mps` (macOS GPU), `cuda` (NVIDIA GPU).

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
