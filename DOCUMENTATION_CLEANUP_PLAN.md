# 📄 MECRIS DOCUMENTATION CLEANUP PLAN
**Assessment Date**: October 19, 2025  
**Purpose**: Transform 188 scattered markdown files into structured, maintainable documentation following GitHub Issues workflow

---

## 🔍 **CURRENT DOCUMENTATION CRISIS**

### **Scale of the Problem**
- **188 markdown files** scattered across the repository
- **12 GitHub Issues** to manage all project work
- **Documentation debt** from pre-GitHub-Issues era
- **Schizophrenic patterns** mixing planning docs, status updates, handoffs, and permanent documentation

### **Key Findings**
1. **Boris-Fiona-Walker module** shows excellent documentation practices (post-GitHub-Issues)
2. **Main repository** contains documentation chaos from development without issue tracking
3. **Multiple overlapping planning documents** (ROADMAP.md, docs/TODO.md, docs/ROADMAP.md)
4. **Closed issues ready for retirement** (#19, #13 - Boris & Fiona system completed)
5. **Embedded issues in documents** that should be converted to GitHub Issues

---

## 📋 **DOCUMENTATION AUDIT RESULTS**

### **Retirement Candidates** (Ready for attic/cold-storage)

#### 1. **BORIS_FIONA_HANDOFF.md** - IMMEDIATE RETIREMENT
- **References**: Closed issues #19 and #13
- **Status**: Both issues closed October 19, 2025
- **Content**: Handoff instructions now obsolete
- **Information Migration**: All technical details preserved in boris-fiona-walker/ module docs

#### 2. **Documents with Embedded Issues** (Convert to GitHub Issues first)
- `DOCUMENTATION_ARCHITECTURE_PLAN.md` - Contains 15+ checkbox items that should be GitHub Issues
- `GPT_SAYS.md` - Contains "Bug: Beeminder Data Incorrect" and task lists
- `ANTHROPIC_COST_USAGE_NOTES.md` - Contains implementation tasks
- `NEXT_PRIORITIES.md` - Should be GitHub Issues, not a document

#### 3. **Duplicate Planning Documents** (Consolidate/Retire)
- Multiple `ROADMAP.md` files (root and docs/)
- Multiple `TODO.md` files with overlapping content
- Status update files that are now historical

---

## 🏗️ **PROPOSED DOCUMENTATION ARCHITECTURE**

### **Permanent Documentation Tree** (Never Retire)
```
/
├── README.md                    # Project overview and quick start
├── CLAUDE.md                    # Claude runtime context (permanent)
├── ROADMAP.md                   # Single source of truth for roadmap
└── docs/
    ├── ARCHITECTURE.md          # System architecture
    ├── DEPLOYMENT.md            # Production deployment guide
    ├── DEVELOPMENT.md           # Development setup
    ├── API.md                   # API documentation
    └── TROUBLESHOOTING.md       # Common issues and solutions
```

### **Module-Specific Documentation** (Following Boris-Fiona pattern)
```
boris-fiona-walker/
├── README.md                    # Module overview
├── DEPLOYMENT.md               # Module deployment
├── TESTING.md                  # Testing strategy
├── SECURITY_ASSESSMENT_REPORT.md # Security documentation
└── .github/                    # Module-specific workflows
```

### **Attic Structure** (Retirement system)
```
attic/
├── README.md                   # Retirement protocol
├── cold-storage/               # Retired documents
│   ├── README.md              # Cold storage protocol
│   ├── .retired-*.md          # Retirement records
│   └── [retired-documents]    # Actual retired content
└── [reference-materials]       # Historical context with ongoing value
```

---

## 🔄 **CLEANUP EXECUTION PLAN**

### **Phase 1: Immediate Retirements** (This week)
1. **Create retirement record for BORIS_FIONA_HANDOFF.md**
   - Document references to issues #19 and #13
   - Note information migration to boris-fiona-walker/ module
   - Move to attic/cold-storage/

2. **Consolidate duplicate roadmaps**
   - Merge root ROADMAP.md and docs/ROADMAP.md
   - Keep single source of truth in root
   - Retire outdated version

### **Phase 2: Issue Extraction** (Next 2 weeks)
1. **Extract embedded issues from documents**
   - DOCUMENTATION_ARCHITECTURE_PLAN.md → 10+ GitHub Issues
   - GPT_SAYS.md → Bug reports and tasks
   - ANTHROPIC_COST_USAGE_NOTES.md → Implementation tasks
   - NEXT_PRIORITIES.md → Priority GitHub Issues

2. **Convert task lists to GitHub Issues**
   - Each checkbox becomes a GitHub Issue
   - Add appropriate labels (enhancement, bug, documentation)
   - Link related issues with cross-references

### **Phase 3: Architecture Restructuring** (Next month)
1. **Create permanent documentation structure**
   - Establish core docs/ directory
   - Migrate essential content to permanent locations
   - Remove redundant/outdated information

2. **Establish retirement protocol**
   - Document clear criteria for retirement
   - Create templates for retirement records
   - Train system for ongoing maintenance

---

## 📊 **SUCCESS METRICS**

### **Quantitative Goals**
- **Reduce from 188 to <50 markdown files**
- **Convert 30+ embedded tasks to GitHub Issues**
- **Establish 5-10 permanent documentation files**
- **Retire 50+ obsolete documents**

### **Qualitative Goals**
- **Clear separation** between permanent docs and ephemeral issues
- **Single source of truth** for each type of information
- **New contributor onboarding** in <5 minutes
- **Documentation supports autonomous deployment** vision

---

## 🏷️ **GITHUB ISSUES NEEDED**

### **High Priority** (Convert embedded issues)
1. **Documentation Architecture Complete** - Track restructuring progress
2. **Beeminder Data Accuracy Bug** - From GPT_SAYS.md
3. **Anthropic Cost Tracking Implementation** - From ANTHROPIC_COST_USAGE_NOTES.md
4. **Production Deployment Documentation** - From multiple planning docs

### **Medium Priority** (Strategic improvements)
1. **SMS Interface Architecture Design** - From ROADMAP.md vision
2. **Autonomous Deployment System** - From architectural planning
3. **Knowledge Base Integration** - From ROADMAP.md goals

---

## 🎯 **IMMEDIATE NEXT STEPS**

1. **Create retirement record for BORIS_FIONA_HANDOFF.md** ✅ Ready now
2. **File GitHub Issues for major embedded task lists** ✅ Ready now
3. **Consolidate duplicate roadmaps into single source of truth** ✅ Ready now
4. **Establish permanent documentation structure** - Next iteration
5. **Begin systematic retirement of obsolete planning documents** - Ongoing

---

## 💬 **RECOMMENDATIONS**

**Immediate Actions**:
1. Start with BORIS_FIONA_HANDOFF.md retirement (clear win)
2. Extract high-value issues from DOCUMENTATION_ARCHITECTURE_PLAN.md
3. Consolidate roadmap duplication

**Strategic Vision**:
- Follow boris-fiona-walker/ as the documentation gold standard
- Every planning task becomes a GitHub Issue
- Only permanent architecture and operational docs survive
- Retirement protocol becomes routine part of issue closure

**Long-term Goal**: 
Transform Mecris from "documentation chaos with some code" to "clean codebase with issues-driven development and permanent operational documentation."

---

*This cleanup plan supports the ultimate vision of Mecris as an autonomous SMS-based accountability system where documentation serves operators and contributors, not accumulated planning debt.*