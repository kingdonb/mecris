# Prompt 4 — guarded release verification and `0.0.1` tag

Run this only after the Akamai deployment has been built, deployed, and verified. The release tag is a consequence of demonstrated stability, not a goal to reach by optimism.

Do not create or move the tag until every gate below is recorded with evidence:

- the intended Akamai API base URL is confirmed from deployment configuration and Android/Pi logs;
- authenticated read-only smoke tests pass against the deployed artifact;
- the Android app completes the canonical Beeminder sync without requiring a local STDIO MCP server;
- at least one repeat sync succeeds after a clean app/harness restart, proving this was not a warm-process accident;
- relevant auth, database, Beeminder, and service-mesh dependencies are reachable and no unexplained errors remain;
- no known release-blocking route, schema, migration, or deployment mismatch remains;
- repository tests, build checks, and deployment validation pass for the exact source revision being released;
- the working tree and generated artifacts are understood, with no accidental secrets or unrelated changes;
- release notes state known caveats, including Fermyon limitations and routes/components intentionally not deployed.

When all gates pass:

1. Confirm the exact commit SHA running at Akamai.
2. Confirm that `0.0.1` does not already exist or point elsewhere. Never move an existing tag silently.
3. Create the annotated tag `0.0.1` on the verified commit using the repository's normal release procedure.
4. Push the tag only through the normal authorized mechanism.
5. Verify that the remote tag resolves to the same commit and the deployment record references that revision.
6. Report the tag, commit, deployment timestamp, smoke-test evidence, Android sync evidence, and remaining caveats.

If any gate is unknown or fails, do **not** tag. Return `RELEASE BLOCKED` with the failed gate and one smallest next action. Do not force-update or delete a tag, rewrite history, or tag a merely buildable but unverified artifact.