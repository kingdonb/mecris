# Mecris Environment Management: Tools & Isolated Builds

This project enforces **Total Isolation** for all Python-based tools and WASM components. We use **`uv`** as the primary engine for virtual environment management and dependency injection.

## 🏁 Core Philosophy: Total Hermeticity

1.  **No Shared Environments**: No tool in the `tools/` directory should ever share a virtual environment with the root project or another tool.
2.  **Explicit Python Versions**: We target **Python 3.13** for modern WASM components and **Python 3.12** for stable production tools like TalkType.
3.  **Disposable Venvs**: Every build or tool setup should be capable of being nuked (`rm -rf .venv`) and recreated instantly via `uv`.

---

## 🎙️ TalkType Environment (`tools/talktype`)

TalkType requires a specific set of dependencies for local audio processing and Whisper transcription.

### Setup & Recovery
If TalkType stops working or reporting module errors:
```bash
cd tools/talktype
rm -rf .venv
uv venv --python 3.12
. .venv/bin/activate
uv pip install -r talktype-repo/requirements.txt
```

### Why Python 3.12?
TalkType uses `faster-whisper` and various native audio libraries (`portaudio`) that have optimized, stable binaries for Python 3.12 on macOS.

---

## 🏗️ WASM Build Strategy (Universal Clean Build)

Our Python-to-WASM migration (Spin SDK v4) uses an aggressive isolation strategy in `spin.toml` to prevent "Environment Pollution" during the componentization phase.

### The "Kitchen Sink" Command
Every Python component in this project (e.g., `review-pump-py`, `log-message-py`) is built using this pattern:

```toml
[component.example.build]
command = """
  find . -name '.venv*' -type d -exec rm -rf {} + && \
  find . -name '__pycache__' -type d -exec rm -rf {} + && \
  uv venv .venv_build --clear --python 3.13 && \
  . .venv_build/bin/activate && \
  uv pip install componentize-py==0.23.0 spin-sdk==4.0.0 && \
  componentize-py -w spin:up/http-trigger@4.0.0 \
    componentize -p . -p .venv_build/lib/python3.13/site-packages app -o component.wasm
"""
```

### Why this level of isolation?
- **Avoids SyntaxErrors**: `componentize-py` sometimes scans parent directories and finds unrelated `.venv` folders, causing import collisions.
- **Ensures Freshness**: The `--clear` flag and `rm -rf` steps ensure that no "Zombie" code or stale `__pycache__` is baked into the immutable WASM binary.
- **Reproducibility**: By explicitly installing specific versions of the SDK and compiler inside a fresh environment *at build time*, we achieve near-perfect reproducibility.

---

## 🛠️ Global UV Cheat Sheet

| Goal | Command |
| :--- | :--- |
| **Create Venv** | `uv venv --python 3.13` |
| **Install Requirements** | `uv pip install -r requirements.txt` |
| **Run Tool w/o Install** | `uv run --with <pkg> <command>` |
| **Check Environment** | `uv pip list` |

---
*Last Updated: 2026-04-24*
