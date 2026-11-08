# Performance Fix Candidates

This document contains 5 candidates for performance improvements that would enhance application speed, reduce latency, and optimize resource utilization.

## AC-1: Unbounded Query Result Sets Without Pagination

**File:** `app/api/endpoints.py`

**Issue:** Several API endpoints return unbounded result sets from database queries, causing memory exhaustion and slow response times when tables grow large.

**Fix:** Implement cursor-based pagination with configurable page sizes (default 100, max 1000) and add `LIMIT`/`OFFSET` to all list endpoints to prevent unbounded memory allocation.

---

## AC-2: Synchronous Database Calls in Request Thread Pool

**File:** `app/services/database.py`

**Issue:** Database queries execute synchronously in the main request thread pool, blocking concurrent request processing and causing thread pool starvation under load.

**Fix:** Move database operations to a dedicated async thread pool or use async database drivers (e.g., asyncpg, aiosqlite) to allow concurrent request handling during I/O waits.

---

## AC-3: Missing Database Connection Pool Configuration

**File:** `app/database.py`

**Issue:** Database connection pool uses default sizing (10 connections) without tuning for workload characteristics, causing connection wait queues and increased latency under concurrent load.

**Fix:** Configure connection pool size based on available memory and CPU cores (recommended: 20-50 connections), add connection timeout settings, and implement connection leak detection to prevent pool exhaustion.

---

## AC-4: N+1 Query Pattern in User Profile Serialization

**File:** `app/serializers/user.py`

**Issue:** User profile serialization triggers individual database queries for each related object (posts, comments, notifications), resulting in O(n) queries for n users instead of a single JOIN query.

**Fix:** Use eager loading with `select_related()` (PostgreSQL) or `prefetch_related()` (MongoDB) to fetch all related objects in a single query, reducing database round-trips from O(n) to O(1).

---

## AC-5: Uncompressed API Response Payloads

**File:** `app/middleware/compression.py`

**Issue:** API responses are transmitted without compression, causing large payload sizes (especially for JSON with nested objects) and increased network latency for clients.

**Fix:** Enable gzip/brotli compression for API responses larger than 1KB, add `Content-Encoding` headers, and configure compression level to balance CPU usage vs. bandwidth savings.

---
