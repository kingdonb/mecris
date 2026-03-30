---
name: talktype-mirror
description: Manage the synchronization and IP separation between the public talktype-repo and the internal Urmanac mirror. Use when developing features across public and internal boundaries, ensuring Urmanac-specific context remains isolated while generic improvements are shared.
---

# Skill: talktype-mirror

Expert guide for managing the dual-repo setup for the TalkType project, ensuring IP separation and synchronization between public and internal mirrors.

## 🛠️ Workflow

### 1. Identify Context
Verify which repository is the target before starting work.
- **Public:** `mecris/tools/talktype/talktype-repo/`
- **Internal Mirror:** `mecris/tools/talktype/talktype/talktype-repo/`

### 2. Vetted Sync (Public -> Internal)
1. Fetch changes from the Public repository.
2. Review new commits for generic value.
3. Merge/Cherry-pick into the Internal mirror to keep it current.

### 3. Vetted Sync (Internal -> Public)
1. Identify generic improvements (bug fixes, performance tuning).
2. **MANDATORY REVIEW:** Ensure no Urmanac-specific "notes", security context, or server aliases (e.g., `netmoom`) are included.
3. Apply to the Public repository.

## 🛡️ Safeguards & IP Isolation
- **Urmanac Boundaries:** Keep internal-only documents (security reviews, private roadmaps) in the `talktype/` root directory, OUTSIDE of the git repositories.
- **No Submodules:** Do NOT attempt to convert the nested `talktype/talktype-repo/` folder into a git submodule.
- **Production Readiness:** Use the public Helm chart for all production-aligned work.

## 📦 Helm & Deployment
- Base charts are located in `talktype-charts/` (sandboxed and gitignored).
- Use `readme-generator-for-helm` to maintain documentation.
- The Helm chart maintains a single public remote.
