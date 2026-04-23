---
title: "🚀 Narrator Context Caching Strategy"
description: "The narrator context endpoint currently takes 10+ seconds due to redundant external API calls and lack of caching. This document outlines a comprehensive caching strategy that will:"
tags: ["narrator", "context", "caching", "strategy"]
date: "2025-08-04"
---

# 🚀 Narrator Context Caching Strategy

> **Performance optimization plan to reduce `/narrator/context` latency from 10+ seconds to <2 seconds**

## 🎯 Executive Summary

The narrator context endpoint currently takes 10+ seconds due to redundant external API calls and lack of caching. This document outlines a comprehensive caching strategy that will:

- **Eliminate triple redundancy** in Beeminder API calls
- **Cache expensive operations** with intelligent invalidation  
- **Maintain data freshness** with appropriate TTLs
- **Support stateless deployment** (Spin app ready)

**Target Performance:** Reduce latency from 10+ seconds to <2 seconds for cached requests.

---

## 🔍 Current Performance Analysis

### Data Sources in `/narrator/context`

| Component | Type | Current Behavior | Est. Latency | Cache Status |
|-----------|------|------------------|--------------|--------------|
| **Beeminder Goals** | Network API | Called 3x per request | 3-6 seconds | ❌ None |
| **Obsidian Todos** | Network MCP | Vault scan + file reads | 2-4 seconds | ❌ None |
| **Local Goals** | SQLite | Direct query | <50ms | ✅ N/A |
| **Budget Status** | SQLite | Direct query | <50ms | ✅ N/A |
| **Daily Activity** | Network API | Single call | 200-500ms | ✅ 1h TTL |

### Critical Issues Identified

1. **🔥 TRIPLE REDUNDANCY**: `beeminder_client.get_all_goals()` called 3 times:
   - Once by `get_all_goals()`
   - Again by `get_emergencies()` 
   - Again by `get_runway_summary()`

2. **🔥 OBSIDIAN VAULT SCANNING**: Full vault search for every todo request:
   - Search for `"- [ ]"` patterns (entire vault)
   - Search for `"- [x]"` patterns (entire vault)
   - Read content of every matching file

3. **🔥 NO INTERMEDIATE CACHING**: No caching between expensive operations

---

## 🛠️ Caching Strategy by Component

### 1. Beeminder Goals Cache

**Priority:** 🔥 **CRITICAL** (Highest impact)

**Current Problem:**
```python
# In get_narrator_context() - CALLED 3 TIMES!
beeminder_status = await beeminder_client.get_all_goals()      # Call 1
emergencies = await beeminder_client.get_emergencies()         # Call 2 → calls get_all_goals() again!
goal_runway = await beeminder_client.get_runway_summary()      # Call 3 → calls get_all_goals() again!
```

**Solution: Single Call + Derived Data**
```python
# Cache the base data once
beeminder_goals = await get_cached_beeminder_goals()

# Derive other views from cached data
beeminder_status = beeminder_goals  
emergencies = derive_emergencies(beeminder_goals)
goal_runway = derive_runway_summary(beeminder_goals, limit=4)
```

**Cache Configuration:**
- **TTL:** 30 minutes (Beeminder updates infrequently)
- **Key:** `beeminder_goals_{username}`
- **Invalidation:** Time-based + manual endpoint for emergencies
- **Fallback:** Return stale data on API failure, flag as stale

**Implementation Location:** `beeminder_client.py`

### 2. Obsidian Todos Cache

**Priority:** 🔥 **HIGH** (Second highest impact)

**Current Problem:**
```python
# Scans entire vault TWICE per request
checkbox_matches = await self.search_vault("- [ ]")        # Full vault scan
completed_matches = await self.search_vault("- [x]")       # Full vault scan  
# Then reads EVERY matching file individually
```

**Solution: Cached Todo Index**
- Cache the complete todo index, not individual searches
- Include file modification times for smart invalidation
- Pre-parse and structure todo data

**Cache Configuration:**
- **TTL:** 15 minutes (todos change frequently during work sessions)
- **Key:** `obsidian_todos_{vault_hash}`
- **Invalidation:** File modification time tracking (when possible)
- **Fallback:** Return stale data if Obsidian MCP unavailable

**Implementation Location:** `obsidian_client.py`

### 3. Daily Activity Cache

**Priority:** ✅ **DONE** (Already implemented)

**Current Status:** ✅ Working well with 1-hour cache

**Notes:** This is our success model - extend this pattern to other components.

### 4. Narrator Context Assembly Cache

**Priority:** 🟡 **MEDIUM** (Performance optimization)

**Strategy:** Cache the final assembled context response

**Cache Configuration:**
- **TTL:** 5 minutes (short, for responsiveness)
- **Key:** `narrator_context_{hash_of_inputs}`
- **Invalidation:** Automatic when any underlying cache expires
- **Purpose:** Serve repeated requests instantly

---

## 🏗️ Implementation Architecture

### Phase 1: In-Memory Caching (Start Here)

**Target:** Quick wins with minimal infrastructure changes

```python
# Shared cache structure in mcp_server.py
app_cache = {
    "beeminder_goals": {
        "data": None,
        "expires": None,
        "last_check": None
    },
    "obsidian_todos": {
        # Similar structure
    }
}
```

**Benefits:**
- ✅ Immediate performance gains
- ✅ Simple to implement
- ✅ Works with current architecture
- ✅ Testable and debuggable

**Limitations:**
- ❌ Lost on process restart
- ❌ No sharing between instances

### Phase 2: Persistent Caching (Future)

**Target:** Spin app deployment readiness

**Options Considered:**
1. **SQLite Cache Table** (Recommended)
   - ✅ Already using SQLite for other data
   - ✅ ACID transactions
   - ✅ Simple expiration logic
   - ✅ Survives restarts

2. **Redis** (If needed later)
   - ✅ Distributed caching
   - ✅ Advanced features
   - ❌ Additional infrastructure dependency

3. **File-based Cache**
   - ✅ Simple
   - ❌ Concurrency issues
   - ❌ Manual cleanup needed

---

## 📋 Implementation Plan

### Phase 1: Emergency Fixes (1-2 hours)

**Goal:** Eliminate triple redundancy immediately

1. **Refactor Beeminder Client**
   - [ ] Create `get_cached_beeminder_goals()` method
   - [ ] Modify `get_emergencies()` to accept pre-fetched goals
   - [ ] Modify `get_runway_summary()` to accept pre-fetched goals
   - [ ] Update `/narrator/context` to call once + derive

**Expected Improvement:** 10 seconds → 6 seconds (40% reduction)

### Phase 2: Beeminder Goals Caching (2-3 hours)

2. **Add In-Memory Beeminder Cache**
   - [ ] Implement cache storage structure
   - [ ] Add TTL checking logic  
   - [ ] Add cache invalidation endpoint
   - [ ] Add fallback logic for API failures

**Expected Improvement:** 6 seconds → 3 seconds (50% reduction)

### Phase 3: Obsidian Todos Caching (3-4 hours)

3. **Add In-Memory Obsidian Cache**
   - [ ] Implement cached todo index
   - [ ] Add smart invalidation (if file modification times available)
   - [ ] Add fallback logic for MCP server failures

**Expected Improvement:** 3 seconds → 1.5 seconds (50% reduction)

### Phase 4: Optimization & Monitoring (2-3 hours)

4. **Final Optimizations**
   - [ ] Add narrator context assembly cache (5 min TTL)
   - [ ] Add cache hit/miss metrics to `/health` endpoint
   - [ ] Add cache management endpoints (`/cache/status`, `/cache/clear`)
   - [ ] Performance testing and tuning

**Expected Final Performance:** <2 seconds consistently

---

## 🎯 Cache TTL Recommendations

| Component | TTL | Rationale |
|-----------|-----|-----------|
| **Beeminder Goals** | 30 min | Goals update infrequently, safebuf changes slowly |
| **Obsidian Todos** | 15 min | Active during work sessions, needs freshness |
| **Daily Activity** | 1 hour | ✅ Already working well |
| **Narrator Assembly** | 5 min | Final response cache for rapid repeated access |

### Emergency Override

- **Manual cache invalidation** endpoints for urgent updates
- **Beemergency detection** can force immediate cache refresh
- **Health check failures** can trigger cache invalidation

---

## 🔒 Cache Safety Considerations

### 1. Graceful Degradation
```python
try:
    data = await get_cached_data()
except Exception:
    # Always fall back to live data for critical systems
    data = await get_live_data()
```

### 2. Stale Data Handling
- Mark stale data with timestamps
- Include staleness warnings in responses
- Set maximum stale age limits

### 3. Cache Consistency
- Version cache entries to handle schema changes
- Use content hashing for cache keys where appropriate
- Clear related caches when dependencies change

---

## 📊 Success Metrics

### Performance Targets
- **Latency:** <2 seconds for 95% of cached requests
- **Cache Hit Rate:** >80% during normal usage
- **API Call Reduction:** >70% reduction in external calls

### Monitoring Points
- Response time distribution
- Cache hit/miss ratios by component
- External API call frequency
- Error rates and fallback usage

---

## 🚀 Future Considerations

### Spin App Readiness
- Current Phase 1 (in-memory) → Migration to SQLite cache tables
- Stateless design ensures no session affinity needed
- Cache warming strategies for cold starts

### Advanced Features (Post-Launch)
- **Smart prefetching** based on usage patterns
- **Incremental updates** for large datasets
- **Background refresh** to avoid cache misses
- **Cache sharding** for multi-user scenarios

---

## 💡 Key Insights

1. **Biggest Win:** Eliminating triple redundancy in Beeminder calls provides immediate 40% improvement
2. **Caching Pattern:** The existing daily activity cache is the perfect model to extend
3. **Risk Mitigation:** Always fall back to live data - performance improvement should never compromise reliability
4. **Progressive Enhancement:** Each phase provides independent value, can be deployed incrementally

**Next Action:** Start with Phase 1 to get immediate 40% performance improvement with minimal risk.