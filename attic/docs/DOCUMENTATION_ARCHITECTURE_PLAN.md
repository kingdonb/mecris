# 🏗️ Mecris Documentation Architecture Plan

**Date**: October 19, 2025  
**Purpose**: Transform scattered documentation into structured, maintainable knowledge base supporting long-term vision  
**Vision**: Mecris as autonomous SMS-based accountability system

## 🎯 Long-Term Vision & Architecture

### Ultimate Goal: Autonomous SMS Accountability System
- **SMS Interface**: Users interact via text messages processed through persistent message queue
- **Always-On Architecture**: Mecris runs autonomously, users don't know/care about technical details
- **Invisible Operation**: No Claude Code CLI, no manual server management
- **Pure Accountability**: Focus on goals, budget, and life management through conversational SMS

### Current State vs Future State
| Current | Future |
|---------|--------|
| Claude Code CLI interaction | SMS conversation interface |
| Manual server management | Autonomous deployment |
| Local development setup | Production containerized system |
| Budget tracking via API | Seamless financial integration |
| Mixed documentation chaos | Clean, permanent documentation tree |

## 📚 Permanent Documentation Tree

Based on the vision and current state, here's the proposed permanent structure:

### **Core Permanent Documents** (Never Retire)
```
/
├── README.md               # Quick start, what Mecris is, how to use it
├── CLAUDE.md              # Core mission & narrator context (KEEP AS-IS)
├── ARCHITECTURE.md        # System design, SMS vision, deployment patterns
└── docs/
    ├── DEPLOYMENT.md      # Production deployment guide
    ├── DEVELOPMENT.md     # Local development setup
    ├── API.md             # MCP endpoints and SMS interface specs  
    ├── OPERATIONS.md      # Running, monitoring, troubleshooting
    └── ROADMAP.md         # Strategic priorities and milestones
```

### **Reference Documents** (Long-term Archive)
```
attic/
├── README.md              # Archive management guide
├── INTEGRATIONS.md        # Beeminder, Twilio, AWS setup guides
├── TESTING.md             # Test suites and validation procedures
└── cold-storage/          # Retired docs with .retired-*.md records
    └── README.md          # Retirement protocol
```

## 🗂️ Document Classification & Migration Strategy

### **PERMANENT TREE** - Core Documentation
**Criteria**: Essential for understanding, operating, or developing Mecris

| Document | Action | Rationale |
|----------|--------|-----------|
| `README.md` | **CONSOLIDATE** | Merge quick start info, remove redundancy |
| `CLAUDE.md` | **KEEP AS-IS** | Perfect mission statement, single source of truth |
| `ARCHITECTURE.md` | **CREATE NEW** | Consolidate system design from scattered specs |
| `docs/DEPLOYMENT.md` | **CREATE NEW** | Production deployment procedures |
| `docs/DEVELOPMENT.md` | **CREATE NEW** | Local development and contribution guide |
| `docs/API.md` | **CREATE NEW** | MCP endpoints and future SMS API |
| `docs/OPERATIONS.md` | **CREATE NEW** | Running, monitoring, troubleshooting |
| `docs/ROADMAP.md` | **CREATE NEW** | Strategic priorities toward SMS vision |

### **ARCHIVE TREE** - Reference Materials
**Criteria**: Valuable for reference but not actively maintained

| Document | Action | Rationale |
|----------|--------|-----------|
| `attic/INTEGRATIONS.md` | **CREATE NEW** | Beeminder, Twilio, AWS setup consolidation |
| `attic/TESTING.md` | **CREATE NEW** | Test procedures and validation guides |

### **RETIREMENT CANDIDATES** - Convert to Issues
**Criteria**: Ephemeral planning, status reports, or issue descriptions

| Document | GitHub Issue Title | Retirement Reason |
|----------|-------------------|-------------------|
| `AUTONOMOUS_DEPLOYMENT_PLAN.md` | "Implement Autonomous EC2 Deployment System" | Implementation plan → trackable issue |
| `ENHANCEMENT_ASSESSMENT.md` | "Integrate Tamagotchi Trainer & Stakpak Infrastructure" | Enhancement request → feature issue |
| `FORMALIZATION_PLAN.md` | "Complete Mecris Production Formalization" | Project plan → milestone with sub-issues |
| `ANTHROPIC_COST_USAGE_NOTES.md` | "Implement Cost Tracking & Budget Alerts" | Implementation notes → feature issue |
| `docs/TODO.md` | Multiple issues | Todo list → individual trackable issues |
| `docs/SYSTEM_STATUS.md` | "System Health Dashboard" | Status report → operational issue |
| `NEXT_PRIORITIES.md` | Multiple issues | Priority list → labeled issues |
| Various spec files | Spec-specific issues | Ad-hoc specs → implementation issues |

### **IMMEDIATE RETIREMENT** - Redundant or Obsolete
**Criteria**: Information already covered elsewhere or outdated

| Document | Action | Information Preserved In |
|----------|--------|-------------------------|
| `CHECK_IN_OCT_19.md` | **RETIRE** | Planning complete, info → issues |
| `GPT_SAYS.md` | **RETIRE** | Session notes, no permanent value |
| Multiple cost tracking docs | **RETIRE** | Consolidate into `ARCHITECTURE.md` |
| Duplicate spec files | **RETIRE** | Best version → permanent docs |

## 🏷️ GitHub Issue Label System

### **Issue Types**
- `documentation` - Documentation work
- `feature` - New functionality 
- `enhancement` - Improvements to existing features
- `production` - Production deployment related
- `architecture` - System design decisions
- `integration` - Third-party service integration

### **Priority Levels**
- `critical` - Production blockers
- `high-priority` - Important for vision realization
- `medium-priority` - Valuable improvements
- `low-priority` - Nice to have

### **Lifecycle Management**
- `retirement-candidate` - Doc scheduled for retirement
- `needs-migration` - Info needs consolidation before retirement
- `blocked` - Waiting on external dependencies

### **Effort Estimation**
- `quick-win` - < 2 hours
- `medium-effort` - 2-8 hours  
- `large-project` - > 8 hours or multi-session

## 🔄 Migration Workflow

### Phase 1: Create Permanent Structure (This Session)
1. **Create attic structure** with retirement protocols
2. **Set up GitHub issue labels** and templates
3. **Create permanent doc stubs** (empty but structured)
4. **Begin high-value migrations** (convert 3-5 key documents to issues)

### Phase 2: Content Consolidation (Next Session)
1. **Write ARCHITECTURE.md** - Consolidate system design
2. **Update README.md** - Clear, focused quick start
3. **Create DEPLOYMENT.md** - Production procedures
4. **Create OPERATIONS.md** - Running and monitoring

### Phase 3: Issue Migration (Ongoing)
1. **Convert planning docs** to GitHub issues
2. **Create retirement records** for each migrated doc
3. **Move retired docs** to cold storage
4. **Update cross-references** in permanent docs

### Phase 4: Maintenance (Ongoing)
1. **Quarterly retirement audits** - Check for new candidates
2. **Issue grooming** - Close completed work, update priorities  
3. **Documentation updates** - Keep permanent docs current
4. **Vision alignment** - Ensure docs support SMS future

## 🎯 Success Metrics

### Short-term (Next 2-4 Sessions)
- [ ] Permanent doc structure established
- [ ] 10+ documents converted to GitHub issues
- [ ] Attic structure with retirement protocol active
- [ ] New contributors can understand Mecris purpose in < 5 minutes

### Medium-term (Next Month)
- [ ] All ephemeral docs converted to issues or retired
- [ ] Production deployment fully documented  
- [ ] SMS integration architecture clearly defined
- [ ] Documentation debt eliminated

### Long-term (3-6 Months)
- [ ] Documentation supports autonomous deployment
- [ ] SMS interface specifications complete
- [ ] Knowledge base enables external contributions
- [ ] Mecris vision clearly communicated to potential users

## 🚨 Risk Mitigation

### **Information Loss Prevention**
- **Retirement Records**: Every retired doc gets `.retired-*.md` with migration info
- **Issue References**: All converted content linked to GitHub issues
- **Archive Access**: Important reference materials stay in `attic/`

### **Maintenance Overhead**
- **Minimal Permanent Tree**: Only essential docs in active maintenance
- **Issue-Based Tracking**: Ephemeral work tracked in GitHub, not files
- **Automated Audits**: Quarterly reviews prevent documentation drift

### **User Experience**
- **Clear Entry Points**: README → specific guides
- **Vision Communication**: Architecture doc explains long-term direction
- **Operational Focus**: Deployment/operations docs for production readiness

---

**Ready to implement this plan immediately. Starting with attic structure and high-value issue creation.**