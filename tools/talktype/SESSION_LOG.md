I've updated the workflow to support Groq's high-speed transcription API.

Session Log: Groq API Integration

Objective: Enable a low-latency transcription path using the Groq Whisper API while maintaining existing local server support.

Changes:
 1. `talktype-repo/talktype.py`:
     * Added `import os` to support environment variable retrieval.
     * Enhanced `transcribe_api` to detect OpenAI-compatible endpoints (Groq/OpenAI).
     * Implemented automatic Authorization header injection using `GROQ_API_KEY` or `OPENAI_API_KEY` from the environment.
     * Cleaned up duplicate `import json` statements.
 2. Makefile:
     * Defined `GROQ_API_URL` (https://api.groq.com/openai/v1/audio/transcriptions) and `GROQ_MODEL` (whisper-large-v3).
     * Added `client-groq` target for one-command access to cloud-based transcription.
     * Included a safety check in the Makefile to ensure `GROQ_API_KEY` is present before launching.
     * Updated the help command to reflect the new workflow.

Verification:
 * User confirmed successful transcription using `make client-groq` with the `whisper-large-v3` model.
 * Verified that the client correctly handles the OpenAI-compatible response format.

Usage:
 1 export `GROQ_API_KEY=...`
 2 make client-groq
