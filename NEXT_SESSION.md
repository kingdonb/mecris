# Next Session: Mecris Local AI Tuning & Identity Alignment

## Context
- **Last Session**: Edge LLM tokens-routing and prompt-based ReAct loop completed for the Hailo-ollama integration.
- **Current State**:
  - **Local Python Harness (`MecrisHarness`)**: Connected to remote Hailo-ollama node (`192.168.2.109:30434`) using `qwen2:1.5b` (HEF hardware-accelerated format).
  - **Ollama Client (`OllamaClient`)**: Configured with `use_native_tools=False` to bypass Oat++ JSON array schemas that caused 500 mapping errors. Added top-level `"system"` parameter extraction to enforce instructions on the C++ API server.
  - **Tool Fallback & Parser**: Added substring JSON block parsing and case-insensitive word matching (`\bget_narrator_context\b`) to catch loose model outputs (like bare `Get_narrator_context` text).
  - **Defensive Pruning**: Added payload pruning for `get_narrator_context` (from 8.4 KB to 2.3 KB), eliminating Hailo NPU cache saturation and 502 Gateway timeouts.
  - **Stdio Event Loop Fix**: Resolved `mcp_stdio_server.py` event loop crash by running asynchronously, preventing uvicorn bind conflicts on `8080`.
  - **Inference Verification**: Live stream run successfully executed: user check status query triggered the NPU, executed local MCP narrator context, pruned payload, and returned goal status (Arabic 0 days, Greek 4/7 days, Groq $1).

## High Priority Goals
1. **Mecris Identity crisis**:
   - Resolve the model's identity confusion (where Qwen2 calls the user "Mecris" or refers to itself in the second person).
   - Update the system instructions and user message formats to inject explicit names (e.g. `User: Kingdon`, `Assistant: Mecris`).
2. **Terminal Emojis & Output Cleanup**:
   - Fix rough emoji rendering in the terminal console (`🎈`, `🗑`, etc.) to provide a clean and polished console UI/UX.
3. **Streaming Token integration**:
   - Integrate token-by-token streaming to `stdout` in `py_harness/mecris_harness.py` to eliminate black-box waiting during prompt evaluation and inference.
4. **HA Kubernetes hosting**:
   - Finalize the Tailnet K8s deployment plan for the permanent Mecris coordination engine (sync-service, database link, scheduler daemon) on the 9-node cluster.

## Notes for the Narrator
- The Hailo 10H local AI pipeline is verified functional.
- Edge memory limitations are successfully managed using token pruning.
- Say hello to the live stream folks and celebrate this major local AI milestone!
