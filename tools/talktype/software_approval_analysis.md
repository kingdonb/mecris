# TalkType Software Analysis for Internal Approval

This document provides a detailed analysis of the `talktype` software, its components, and its dependencies, intended to support a software approval process for use at the Federal Aeronautics and Space Travel (FAST) administration.

## 1. Overview

`talktype` is a "push-to-talk" voice transcription tool. It consists of two main components:

1.  **`talktype.py`:** A client application that runs on the user's machine. It captures audio from the microphone when a hotkey is pressed and sends it for transcription. It then pastes the received text into the active window.
2.  **`whisper_server.py`:** A local web server that hosts the `faster-whisper` speech-to-text model. It receives audio from the client, transcribes it, and returns the text.

The tool is designed to be local-first, meaning the transcription is performed on the user's machine without sending data to external cloud services.

## 2. Python Dependencies

The following table lists all direct and transitive Python dependencies for the `talktype` tool.

| Package | Version | License | Type | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **annotated-doc** | 0.0.4 | MIT | Transitive | Dependency of `fastapi` and `typer`. |
| **annotated-types** | 0.7.0 | MIT | Transitive | Dependency of `pydantic`. |
| **anyio** | 4.12.1 | MIT | Transitive | Dependency of `httpx` and `starlette`. |
| **av** | 16.1.0 | BSD-3-Clause | Transitive | Dependency of `faster-whisper` for audio processing. |
| **certifi** | 2026.1.4 | MPL-2.0 | Transitive | SSL certificates. Dependency of `httpcore`, `httpx`, `requests`. |
| **cffi** | 2.0.0 | MIT | Transitive | For calling C code. Dependency of `sounddevice`. |
| **charset-normalizer** | 3.4.4 | MIT | Transitive | Dependency of `requests`. |
| **click** | 8.3.1 | BSD-3-Clause | Transitive | CLI framework. Dependency of `typer` and `uvicorn`. |
| **ctranslate2** | 4.7.1 | MIT | Transitive | Core of `faster-whisper`. |
| **fastapi** | 0.129.0 | MIT | Direct | Web framework for `whisper_server.py`. |
| **faster-whisper** | 1.2.1 | MIT | Direct | The core speech-to-text engine. |
| **filelock** | 3.24.2 | Unlicense | Transitive | Dependency of `huggingface-hub`. |
| **flatbuffers** | 25.12.19 | Apache-2.0 | Transitive | Dependency of `onnxruntime`. |
| **fsspec** | 2026.2.0 | BSD-3-Clause | Transitive | Filesystem abstraction. Dependency of `huggingface-hub`. |
| **h11** | 0.16.0 | MIT | Transitive | HTTP/1.1 library. Dependency of `httpcore` and `uvicorn`. |
| **hf-xet** | 1.2.0 | Apache-2.0 | Transitive | Hugging Face / XetHub integration. |
| **httpcore** | 1.0.9 | BSD-3-Clause | Transitive | HTTP client core. Dependency of `httpx`. |
| **httpx** | 0.28.1 | BSD-3-Clause | Transitive | HTTP client. Dependency of `huggingface-hub`. |
| **huggingface-hub** | 1.4.1 | Apache-2.0 | Transitive | For downloading models from Hugging Face Hub. |
| **idna** | 3.11 | BSD-3-Clause | Transitive | Internationalized Domain Names for Python. |
| **markdown-it-py**| 4.0.0 | MIT | Transitive | Markdown parser. Dependency of `rich`. |
| **mdurl** | 0.1.2 | MIT | Transitive | Markdown URL library. |
| **mouseinfo** | 0.1.3 | MIT | Transitive | Dependency of `pyautogui`. |
| **mpmath** | 1.3.0 | BSD-3-Clause | Transitive | For floating-point arithmetic. Dependency of `sympy`. |
| **numpy** | 2.4.2 | BSD-3-Clause | Direct | Core numerical library for audio processing. |
| **onnxruntime** | 1.24.1 | MIT | Transitive | Runtime for ONNX models, used by `faster-whisper`. |
| **packaging** | 26.0 | Apache-2.0 or BSD-2-Clause | Transitive | Core Python packaging utilities. |
| **pip** | 26.0.1 | MIT | Transitive | Package installer (dependency of `pipdeptree`). |
| **pipdeptree** | 2.30.0 | MIT | Development | Used for this analysis. Not a runtime dependency. |
| **protobuf** | 6.33.5 | BSD-3-Clause | Transitive | Google's protocol buffers. |
| **pyautogui** | 0.9.54 | MIT | Direct | For simulating keyboard and mouse on macOS/Windows. |
| **pycparser** | 3.0 | BSD-3-Clause | Transitive | C parser in Python. Dependency of `cffi`. |
| **pydantic** | 2.12.5 | MIT | Transitive | Data validation library. Dependency of `fastapi`. |
| **pydantic-core** | 2.41.5 | MIT | Transitive | Core of `pydantic`. |
| **pygetwindow** | 0.0.9 | BSD-3-Clause | Transitive | For window management. Dependency of `pyautogui`. |
| **pygments** | 2.19.2 | BSD-2-Clause | Transitive | Syntax highlighter. Dependency of `rich`. |
| **pymsgbox** | 2.0.1 | BSD-3-Clause | Transitive | Dependency of `pyautogui`. |
| **pynput** | 1.8.1 | LGPL-3.0 | Direct | For listening to global hotkeys. |
| **pyobjc-core** | 12.1 | MIT | Transitive | Python <-> Objective-C bridge for macOS. |
| **pyobjc-framework-applicationservices** | 12.1 | MIT | Transitive | macOS ApplicationServices framework. |
| **pyobjc-framework-cocoa** | 12.1 | MIT | Transitive | macOS Cocoa framework. |
| **pyobjc-framework-coretext** | 12.1 | MIT | Transitive | macOS CoreText framework. |
| **pyobjc-framework-quartz** | 12.1 | MIT | Transitive | macOS Quartz framework. |
| **pyperclip** | 1.11.0 | BSD-3-Clause | Direct | For clipboard operations. |
| **pyrect** | 0.2.0 | BSD-2-Clause | Transitive | Dependency of `pygetwindow`. |
| **pyscreeze** | 1.0.1 | BSD-3-Clause | Transitive | Dependency of `pyautogui`. |
| **python-multipart** | 0.0.22 | Apache-2.0 | Direct | For parsing multipart/form-data. Used by `fastapi`. |
| **pytweening** | 1.2.0 | MIT | Transitive | Tweening functions for animations. Dependency of `pyautogui`. |
| **pyyaml** | 6.0.3 | MIT | Transitive | YAML parser. Dependency of `ctranslate2` and `huggingface-hub`. |
| **requests** | 2.32.5 | Apache-2.0 | Direct | HTTP library. |
| **rich** | 14.3.2 | MIT | Transitive | Rich text and beautiful formatting in the terminal. |
| **rubicon-objc** | 0.5.3 | BSD-3-Clause | Transitive | Dependency of `mouseinfo`. |
| **scipy** | 1.17.0 | BSD-3-Clause | Direct | Scientific library for audio processing. |
| **setuptools** | 82.0.0 | MIT | Transitive | Core Python packaging utilities. |
| **shellingham** | 1.5.4 | MIT | Transitive | For detecting shell environments. |
| **six** | 1.17.0 | MIT | Transitive | Python 2/3 compatibility. Dependency of `pynput`. |
| **sounddevice** | 0.5.5 | MIT | Direct | For audio recording. |
| **starlette** | 0.52.1 | BSD-3-Clause | Transitive | ASGI framework. Core of `fastapi`. |
| **sympy** | 1.14.0 | BSD-3-Clause | Transitive | Symbolic mathematics library. Dependency of `onnxruntime`. |
| **tokenizers** | 0.22.2 | Apache-2.0 | Transitive | Tokenization library from Hugging Face. |
| **tqdm** | 4.67.3 | MPL-2.0 and MIT | Transitive | Progress bar library. |
| **typer** | 0.23.1 | MIT | Transitive | CLI framework. |
| **typer-slim** | 0.23.1 | MIT | Transitive | Dependency of `huggingface-hub`. |
| **typing-extensions** | 4.15.0 | Python Software Foundation License | Transitive | Backports for the `typing` module. |
| **typing-inspection** | 0.4.2 | MIT | Transitive | Runtime type inspection. |
| **urllib3** | 2.6.3 | MIT | Transitive | HTTP client. Dependency of `requests`. |
| **uvicorn** | 0.40.0 | BSD-3-Clause | Direct | ASGI server for `fastapi`. |

## 3. System-Level Dependencies

`talktype` also depends on external command-line tools and system libraries, depending on the operating system.

*   **Linux:**
    *   `xdotool`: For window management and simulating key presses.
    *   `xclip`: Used by `pyperclip` for clipboard access.
    *   `xprop`: For identifying window types.
    *   `PortAudio`: The `sounddevice` library is a wrapper around a native audio library. On Linux, this is typically PortAudio (`libportaudio2`).

*   **macOS:**
    *   `osascript`: To execute AppleScript for window management (standard OS component).
    *   `CoreAudio`: The native audio framework used by `sounddevice` (standard OS component).

*   **Windows:**
    *   `user32.dll`: For window management (standard OS component).
    *   `WASAPI`: The native audio framework used by `sounddevice` (standard OS component).

## 4. License Analysis

The majority of the dependencies use permissive open-source licenses like **MIT**, **BSD (2-Clause and 3-Clause)**, and **Apache 2.0**. These licenses generally allow for use, modification, and distribution (including in proprietary and commercial software) with minimal requirements (usually just attribution).

A few licenses are worth noting:

*   **Mozilla Public License 2.0 (MPL-2.0):** Used by `certifi` and `tqdm`. The MPL is a "weak copyleft" license. It requires that modifications to MPL-licensed files be made available under the MPL. However, it allows the MPL-licensed code to be combined with proprietary code in a larger work. Using these libraries as-is should not pose a problem.
*   **LGPL-3.0 (Lesser General Public License):** Used by `pynput`. The LGPL allows the library to be linked with a proprietary application, provided that the library itself remains under the LGPL. If `pynput` is dynamically linked (which is the standard way Python packages are used), this is generally acceptable. If `talktype` were to be distributed as a single frozen executable, this would require more careful analysis to ensure compliance.
*   **Python Software Foundation License (PSFL):** Used by `typing-extensions`. This is a permissive, BSD-style license that is compatible with the GPL.

## 5. Approval Considerations for FAST administration

1.  **Core Functionality is Local:** The tool's primary function (audio recording and transcription) is performed entirely on the local machine. No user data is sent to third-party cloud services. This is a significant security and privacy advantage.
2.  **Model Downloading:** The `faster-whisper` library, on its first run, will download the selected speech-to-text model from `huggingface.co`. This is a one-time operation. The source of these models should be considered. For a secure environment, these models could be pre-downloaded and staged from a trusted location.
3.  **Permissive Licensing:** The vast majority of the Python dependencies are under permissive licenses (MIT, BSD, Apache 2.0) that are widely accepted for use in government and corporate environments.
4.  **Copyleft Licenses (MPL/LGPL):** The use of `certifi` (MPL-2.0), `tqdm` (MPL-2.0), and `pynput` (LGPL-3.0) should be reviewed. For the intended use case (running the Python scripts directly), these licenses are unlikely to pose a problem. If the tool were to be modified or re-distributed, the terms of these licenses would need to be followed.
5.  **System Dependencies:** The tool relies on common system utilities (`xdotool` on Linux, `osascript` on macOS) and standard audio libraries. These are well-understood components. The non-standard ones (like `xdotool`) would need to be approved and installed on Linux systems.

**Recommendation:**

`talktype` appears to be a relatively low-risk tool from a software supply chain perspective, due to its local-first design and the predominantly permissive licenses of its dependencies. The primary points of review for a FAST approval board would be:

*   The source and integrity of the pre-trained models downloaded from Hugging Face Hub.
*   The terms of the MPL-2.0 and LGPL-3.0 licenses for the few packages that use them.
*   The installation of external system dependencies (`xdotool`, etc.) on Linux workstations.
