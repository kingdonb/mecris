# Phase 0: Research (The Majesty Cake)

## Aggregation Logic Strategy
*   **Decision**: Dynamic counting of `is_required_today` instead of hardcoded total logic.
*   **Rationale**: Mecris tracking modalities may evolve over time (e.g., adding a new language or removing a physical requirement temporarily). Hardcoding a denominator of "3" inside the WASM Brain breaks encapsulation. Calculating `required_count` and `completed_count` by mapping over the provided JSON array keeps the module completely robust against architectural shifts in the Host.
*   **Alternatives considered**: Passing a predefined denominator integer in the JSON request. Discarded because it places calculation burden back on the Host, violating the Brain/Body boundary.

## Extism Payload Parsing
*   **Decision**: Use `serde_json` array processing natively within the Extism plugin.
*   **Rationale**: Extism handles JSON naturally. By structuring the input as an array of anonymous goal states (`{ slug, is_required_today, is_completed }`), the WASM does not even need to know *which* goals exist (e.g., "arabic", "steps"). It strictly processes the booleans, maintaining absolute pure-function isolation.
*   **Alternatives considered**: Passing strongly typed fields like `arabic_completed: bool`, `steps_completed: bool`. Discarded as it tightly couples the Brain to the Host's specific feature set.
