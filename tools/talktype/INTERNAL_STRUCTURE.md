# Internal Repository Structure (Urmanac)

## Overview
The `talktype` workspace uses a dual-repo strategy to manage public development and internal "Urmanac" requirements.

## Directory Layout
- `talktype-repo/`: The **Public Repository**. This is the source of truth for all open-source features, bug fixes, and community-aligned development.
- `talktype/`: The **Internal Root**. Contains Urmanac-specific notes, security reviews, and the internal mirror.
    - `talktype/talktype-repo/`: The **Internal Mirror** (Nested Folder). 
        - **IMPORTANT:** This is NOT a git submodule. It is a nested git repository.
        - This folder contains the "un-pushed" commit history and Urmanac-specific experiments.
        - Do NOT attempt to "clean up" or convert this to a submodule. The structure is intentional for sandboxing and IP isolation.

## IP & Licensing (The "Urmanac" Boundary)
- Work done on "Urmanac time" is tracked in the internal mirror.
- Generic improvements should be manually mirrored to the public `talktype-repo/`.
- Sensitive notes (e.g., `OPUS-SECURITY-REVIEW.md`) must stay in the `talktype/` parent directory and never be committed to either the public or internal git repositories.
