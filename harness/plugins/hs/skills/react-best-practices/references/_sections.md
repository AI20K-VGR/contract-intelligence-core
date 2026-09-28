# Sections

This file defines all sections, their ordering, impact levels, and descriptions.
The section ID (in parentheses) is the filename prefix used to group rules.

---

## 1. Eliminating Waterfalls (async)

**Impact:** CRITICAL  
**Description:** Waterfalls: #1 perf killer — each sequential await adds full network latency; eliminating = largest gains.

## 2. Bundle Size Optimization (bundle)

**Impact:** CRITICAL  
**Description:** Reducing initial bundle size improves TTI + LCP.

## 3. Server-Side Performance (server)

**Impact:** HIGH  
**Description:** Optimizing SSR + data fetching eliminates server-side waterfalls, reduces response times.

## 4. Client-Side Data Fetching (client)

**Impact:** MEDIUM-HIGH  
**Description:** Automatic dedup + efficient fetching patterns reduce redundant network requests.

## 5. Re-render Optimization (rerender)

**Impact:** MEDIUM  
**Description:** Reducing unnecessary re-renders minimizes wasted computation, improves UI responsiveness.

## 6. Rendering Performance (rendering)

**Impact:** MEDIUM  
**Description:** Optimizing rendering reduces browser work.

## 7. JavaScript Performance (js)

**Impact:** LOW-MEDIUM  
**Description:** Micro-optimizations in hot paths add up to meaningful gains.

## 8. Advanced Patterns (advanced)

**Impact:** LOW  
**Description:** Advanced patterns for specific cases that require careful implementation.
