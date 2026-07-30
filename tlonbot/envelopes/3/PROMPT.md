# Prompt 2 — orchestrate builds and deployments for the verified Akamai target

Run this only after Prompt 0 has established that Akamai is the intended and reachable deployment target, or has identified a concrete Akamai build/deployment blocker that can be fixed in the existing path.

The objective is to orchestrate the existing build and release path—not to create another Mecris implementation.

1. Identify the exact source revision, branch, build manifest, Spin-SDK/Spin version, Python/Rust runtime, and deployment configuration used by Akamai.
2. Reproduce the build locally or in the repository's existing CI mechanism. Run all existing tests, formatting, type checks, integration tests, and package/deployment validation.
3. Compare the artifact/configuration being built with the artifact/configuration currently running at Akamai. Explain any mismatch.
4. Build the smallest required set of existing components. Do not build every historical API variant just because it exists. Do not add a Fermyon fork while Akamai is the active target.
5. Deploy through the existing documented Akamai mechanism, using already-authorized credentials. Never paste credentials into logs, commits, prompts, or reports.
6. Verify the deployment using the authenticated Akamai smoke test and Android/Pi-harness logs. A successful build is not a successful release; a reachable route is not a completed sync.
7. If deployment is blocked, stop at the blocker and report the exact command/stage/config mismatch and the next reversible action. Do not silently switch providers or roll back to the old API.

Do not create a release tag in this pass unless the release gate in Prompt 3 is satisfied.