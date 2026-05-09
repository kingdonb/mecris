# Area for Expansion 2: Zero-Latency Wasm Edge Compute

## The Unexplored Corner
The current architecture utilizes Fermyon Spin and Extism to compile Python logic into WebAssembly modules, which are then deployed to cloud environments like Akamai. While this is highly scalable, it still relies on the network. Every interaction, every "Nag Ladder" calculation, requires a round-trip to the cloud.

## Future Research Questions
- **Client-Side Wasm Execution:** Since the core logic (like `budget-governor-py/app.py` or the `Review Pump`) is already compiled to Wasm, can these modules be shipped directly to the React/Vite dashboard (`web/`) or the Android application?
- **Zero-Latency Accountability:** By executing the Wasm modules on the user's edge device, Mecris could calculate Beeminder trajectories, adjust language momentum levers, and trigger local push notifications with literally zero network latency and zero cloud compute cost.
- **Local Small Language Models (SLMs):** Could the Wasm edge runtime eventually orchestrate a local, quantized SLM (e.g., via WebGPU or ONNX Runtime) to handle 90% of the daily conversational nagging, falling back to the expensive cloud LLMs only for deep strategic planning?

*This area explores the ultimate decentralization of the cognitive agent, moving from "Cloud-Native" to "Edge-Native."*