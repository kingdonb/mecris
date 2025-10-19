# Attic - Archive and Cold Storage

This directory contains historical documentation and reference materials for the Mecris project, supporting the long-term vision of autonomous SMS-based accountability system.

## Directory Structure

### `/cold-storage/`
**Purpose**: Documents that have been **retired from active use** after issues were resolved and information was migrated to maintained documentation.

**Contents**:
- Resolved issue documentation  
- Redundant planning documents
- Ad-hoc documents superseded by permanent docs
- Retirement records (`.retired-*.md`)

**Protocol**: See `cold-storage/README.md` for complete retirement protocol.

### Root Attic Files
**Purpose**: Reference materials that may have ongoing value but are not part of active development.

**Current Contents**: *(Will be populated as documents are moved from active development)*

## Document Lifecycle

```
Active Docs → GitHub Issues → Issues Resolved → Information Migrated → Cold Storage
     ↓              ↓              ↓                    ↓                  ↓
Permanent Tree   GitHub Issues   Closed Issues     Permanent Docs      Retired Docs
(README.md,      (#10, #11...)   (Completed)      (ARCHITECTURE.md)   (.retired-*.md)
 CLAUDE.md)                                        
```

### Active Documents (Permanent Tree)
- `README.md` - Quick start and overview
- `CLAUDE.md` - Core mission and narrator context  
- `ARCHITECTURE.md` - System design and SMS vision
- `docs/DEPLOYMENT.md` - Production deployment procedures
- `docs/DEVELOPMENT.md` - Local development guide
- `docs/API.md` - MCP endpoints and SMS interface specs
- `docs/OPERATIONS.md` - Running, monitoring, troubleshooting
- `docs/ROADMAP.md` - Strategic priorities and milestones

### Issue Tracking
- **GitHub Issues**: `github.com/kingdonb/mecris/issues`
- **Current Issues**: #9 (access verification), #10 (label system)

### Retirement Candidates
Documents awaiting retirement after issue resolution:
- `FORMALIZATION_PLAN.md` - Production formalization planning
- `ANTHROPIC_COST_USAGE_NOTES.md` - Cost tracking implementation notes
- `docs/TODO.md` - Comprehensive todo list (converting to GitHub issues)
- Various spec and planning documents in `/docs`

### Recently Retired
Documents moved to cold storage (2025-10-19):
- `AUTONOMOUS_DEPLOYMENT_PLAN.md` → Issue #11 (Autonomous EC2 Deployment)
- `ENHANCEMENT_ASSESSMENT.md` → Issue #12 (Tamagotchi & Stakpak Integration)

## Guidelines

### Keep in Attic (Root)
- Configuration examples and templates
- Integration setup references  
- Historical context with ongoing value
- Reference materials for system operations

### Move to Cold Storage
- Issue descriptions now tracked in GitHub
- Status reports superseded by issue tracking
- Ad-hoc documentation replaced by permanent docs
- Planning documents completed and migrated

### Never Archive
- Current operational documentation (permanent tree)
- Active configuration files
- Core mission documents (`CLAUDE.md`)
- Maintained technical references

## Maintenance

- **Quarterly Review**: Evaluate retirement candidates using GitHub issue status
- **Issue Resolution**: Retire documents when GitHub issues close and info is migrated
- **Information Audit**: Ensure migration completeness before retirement
- **Vision Alignment**: Ensure archived materials support SMS accountability vision

## SMS Vision Context

As Mecris evolves toward autonomous SMS-based accountability, archived documentation should preserve the development journey while permanent documentation focuses on:
- Production deployment and operations
- SMS interface specifications  
- Autonomous system architecture
- User experience through text messaging

Historical implementation details and development planning remain valuable in the attic for understanding design decisions and troubleshooting.