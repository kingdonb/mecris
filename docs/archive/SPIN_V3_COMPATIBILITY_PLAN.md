# Spin SDK v3 Compatibility Plan (Legacy Cloud Fork)

## Background
Mecris recently upgraded to Spin SDK v4 and `componentize-py==0.23.0` to support modern async execution in our Python WASM components (`arabic-skip-counter`, `budget-governor-py`, `log-message-py`, `review-pump-py`). 

However, the primary cloud hosting providers (Fermyon Cloud, Akamai) have not yet upgraded their runtimes to support Spin SDK v4. Currently, these components only run successfully in our local Kubernetes environment using the `spin-tainer` executor.

To achieve a stable `v0.0.1` (GA) release that can be deployed to the cloud, we need a compatibility strategy.

## Proposed Strategy: The `legacy-cloud` Branch
Because the difference between SDK v3 and v4 fundamentally changes the entrypoint signature (from synchronous `def handle_request` to `async def handle_request`) and all host-provided APIs (KV, Postgres, HTTP, Variables), a runtime shim is prohibitively complex to maintain in a single codebase.

Instead, we will maintain a temporary `legacy-cloud` branch until the cloud providers catch up.

### Execution Steps
1. **Branch Creation:**
   - Create a `legacy-cloud` branch off `main`.
2. **Downgrade Dependencies:**
   - Revert the WASM build instructions (e.g., in `NEXT_SESSION.md` and any build scripts) to use `componentize-py==0.13.0` (or the last known working v3 version) and `spin-sdk<4.0.0`.
3. **Revert Async Component Logic:**
   - Modify all Python WASM components in `poc/wasm/` on the `legacy-cloud` branch.
   - Change `async def handle_request` back to `def handle_request`.
   - Remove `await` from all Spin SDK calls (`variables.get`, `kv.open_default`, `store.get`, `postgres.query`, `http.send`).
4. **CI/CD Pipeline Adjustment:**
   - Update GitHub Actions deployment workflows to trigger Fermyon/Akamai deployments *only* from the `legacy-cloud` branch.
   - `main` will continue to deploy to the local Kubernetes `spin-tainer` environment.
5. **Backporting Workflow:**
   - As bugs are fixed in `main` leading up to `v0.0.1`, use `git cherry-pick` to backport them to `legacy-cloud`. If the changes touch the WASM components, manually adjust the async syntax during the cherry-pick merge.
6. **Sunsetting:**
   - Once Fermyon and Akamai announce support for Spin SDK v4, we will deploy `main` to the cloud to verify, and then delete the `legacy-cloud` branch.

## Impact on v0.0.1 GA
- **Local/K8s:** Runs cutting-edge SDK v4.
- **Cloud:** Runs stable SDK v3 via the `legacy-cloud` branch.
- **Maintenance:** Introduces minor overhead for backporting WASM component changes, but isolates the main development branch from legacy constraints.