# Cold Storage Documentation Protocol

## Purpose
This directory contains documentation that has been **retired from active use** after the issues they described have been resolved and their information has been properly integrated into Mecris permanent documentation or implemented as features.

## Protocol for Document Retirement

### When to Retire a Document
A document should be moved to cold storage when **ALL** of the following conditions are met:

1. **Issues Resolved**: All GitHub issues referenced in or created from the document have been closed
2. **Information Preserved**: Key information has been migrated to permanent docs (ARCHITECTURE.md, README.md, etc.)
3. **No Active References**: No active workflows, scripts, or processes depend on the document
4. **Redundancy Confirmed**: The document's content is adequately covered by maintained documentation

### Retirement Process

#### 1. Pre-Retirement Checklist
- [ ] Verify all referenced GitHub issues are closed
- [ ] Confirm information migration to permanent docs
- [ ] Check for active references in:
  - Python scripts and configuration files
  - Other documentation files
  - README files and setup instructions
  - Deployment procedures

#### 2. Create Retirement Record
Before moving a document, create a `.retired-FILENAME.md` record:

```markdown
# Retirement Record: ORIGINAL_FILENAME.md

**Retirement Date**: YYYY-MM-DD
**Retired By**: GitHub Copilot / Kingdon Barrett

## Original Purpose
Brief description of what the document covered.

## Issues Addressed
- GitHub Issue #X - Brief description (CLOSED)
- GitHub Issue #Y - Brief description (CLOSED)

## Information Migration
- Key concept A → Migrated to `ARCHITECTURE.md` section X
- Key concept B → Migrated to `README.md` usage section
- Technical details → Migrated to `docs/DEPLOYMENT.md`

## Verification
- [ ] All referenced issues closed
- [ ] No remaining TODOs or FIXMEs
- [ ] Information preserved in permanent docs
- [ ] No active dependencies confirmed
```

#### 3. Move to Cold Storage
```bash
mv DOCUMENT.md attic/cold-storage/
mv .retired-DOCUMENT.md attic/cold-storage/
```

#### 4. Update References
- Remove from main directory listings
- Update any remaining references to point to new location or permanent docs
- Add entry to `attic/README.md` **Retired Documents** section

## Current Candidates for Retirement

### Ready for Retirement (After Issue Resolution)
These documents describe work now tracked in GitHub and should be retired once those issues are closed:

1. **AUTONOMOUS_DEPLOYMENT_PLAN.md**
   - **Contains**: EC2 deployment automation planning
   - **Action Required**: Wait for deployment issue resolution, then migrate architecture info to `docs/DEPLOYMENT.md`
   - **GitHub Issues**: TBD (autonomous deployment issue)

2. **ENHANCEMENT_ASSESSMENT.md**
   - **Contains**: Tamagotchi trainer and Stakpak integration planning
   - **Action Required**: Wait for integration issues resolution
   - **GitHub Issues**: TBD (integration issues)

3. **FORMALIZATION_PLAN.md**
   - **Contains**: Production readiness planning (Aug 1-4, 2025)
   - **Action Required**: Most work complete, migrate remaining items to operations docs
   - **GitHub Issues**: TBD (production readiness issues)

### Under Review
These documents may have ongoing value but need evaluation:

1. **ANTHROPIC_COST_USAGE_NOTES.md** 
   - **Contains**: Cost tracking implementation notes
   - **Action Required**: Extract valuable budget management procedures to `docs/OPERATIONS.md`
   - **Decision Needed**: Keep cost analysis methodology or fully retire?

2. **docs/TODO.md**
   - **Contains**: Large todo list (should be GitHub issues)
   - **Action Required**: Convert todos to GitHub issues, then retire
   - **Decision Needed**: Retire immediately after issue creation

## Retired Documents

*None yet - this section will list documents that have been successfully retired.*

## Archive vs Cold Storage

**Difference**:  
- **`attic/` (Archive)**: Documents with potential ongoing reference value
- **`attic/cold-storage/` (Cold Storage)**: Documents that are redundant with maintained docs and resolved issues

**Rule**: Only move to cold storage when information is **fully preserved** elsewhere and **no ongoing reference value** exists.

## Maintenance

This directory should be reviewed quarterly to ensure:
- Retirement records are accurate and complete
- No documents were prematurely retired
- Information migration was thorough
- Directory doesn't become a dumping ground

## Emergency Recovery

If a cold storage document is needed urgently:
1. Check the retirement record for migration locations
2. If information is insufficient, temporarily restore from cold storage
3. Update the retirement record with lessons learned
4. Re-evaluate retirement decision and improve migration process

## SMS Vision Alignment

As Mecris transitions to autonomous SMS-based accountability, retirement decisions should consider:
- **Production Focus**: Docs supporting SMS deployment stay active
- **Development History**: Implementation journey preserved in cold storage
- **User Experience**: SMS interface specs remain in permanent docs
- **System Architecture**: Core design decisions archived with clear migration paths