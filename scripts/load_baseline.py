#!/usr/bin/env python3
"""Latency baseline for SmartCourse (NFR-P03).

Self-contained — only needs httpx (already in the backend venv). Fires N requests
per endpoint at a fixed concurrency, records each latency, and reports
p50/p95/p99 + throughput as a markdown table to paste into docs/LOAD_BASELINE.md.

Usage (stack must be up):
    venv/bin/python scripts/load_baseline.py
    BASE=http://localhost:8000 venv/bin/python scripts/load_baseline.py
"""
from __future__ import annotations

import asyncio
import os
import time

import httpx

BASE = os.getenv("BASE", "http://localhost:8000")
ADMIN_EMAIL = os.getenv("LOAD_ADMIN_EMAIL", "admin@smartcourse.local")
ADMIN_PASS = os.getenv("LOAD_ADMIN_PASS", "SmartCourseAdmin1!")
STUDENT_EMAIL = os.getenv("LOAD_STUDENT_EMAIL", "load-student@test.com")
STUDENT_PASS = os.getenv("LOAD_STUDENT_PASS", "secret123")


async def _login(client: httpx.AsyncClient, email: str, password: str) -> str:
    r = await client.post(
        f"{BASE}/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def _ensure_student(client: httpx.AsyncClient) -> str:
    await client.post(
        f"{BASE}/api/v1/auth/register",
        json={"email": STUDENT_EMAIL, "password": STUDENT_PASS, "role": "student"},
    )
    return await _login(client, STUDENT_EMAIL, STUDENT_PASS)


def _pct(sorted_ms: list[float], p: float) -> float:
    if not sorted_ms:
        return float("nan")
    k = int(round((p / 100) * (len(sorted_ms) - 1)))
    return sorted_ms[k]


async def _measure(
    client: httpx.AsyncClient,
    label: str,
    path: str,
    headers: dict[str, str],
    n: int,
    concurrency: int,
) -> dict:
    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    errors = 0

    async def one() -> None:
        nonlocal errors
        async with sem:
            t0 = time.perf_counter()
            try:
                r = await client.get(f"{BASE}{path}", headers=headers)
                latencies.append((time.perf_counter() - t0) * 1000)
                if r.status_code >= 400:
                    errors += 1
            except Exception:
                errors += 1

    # warm up (connection setup + cache fill) so we measure steady state
    await asyncio.gather(*[one() for _ in range(min(concurrency, n))])
    latencies.clear()
    errors = 0

    start = time.perf_counter()
    await asyncio.gather(*[one() for _ in range(n)])
    wall = time.perf_counter() - start
    latencies.sort()
    return {
        "label": label,
        "n": n,
        "c": concurrency,
        "errors": errors,
        "p50": _pct(latencies, 50),
        "p95": _pct(latencies, 95),
        "p99": _pct(latencies, 99),
        "rps": n / wall if wall > 0 else float("nan"),
    }


async def main() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        admin = {"Authorization": f"Bearer {await _login(client, ADMIN_EMAIL, ADMIN_PASS)}"}
        student = {"Authorization": f"Bearer {await _ensure_student(client)}"}

        plan = [
            ("GET /health", "/health", {}, 300, 30),
            ("GET /api/v1/courses", "/api/v1/courses?limit=20", admin, 200, 20),
            ("GET /api/v1/courses/recommendations", "/api/v1/courses/recommendations", student, 100, 10),
            ("GET /api/v1/admin/metrics/overview", "/api/v1/admin/metrics/overview", admin, 100, 10),
        ]

        rows = []
        for label, path, headers, n, c in plan:
            rows.append(await _measure(client, label, path, headers, n, c))

    print(f"\nAPI: {BASE}\n")
    print("| Endpoint | n | c | p50 (ms) | p95 (ms) | p99 (ms) | req/s | errors |")
    print("|----------|---|---|----------|----------|----------|-------|--------|")
    for r in rows:
        print(
            f"| `{r['label']}` | {r['n']} | {r['c']} | "
            f"{r['p50']:.1f} | {r['p95']:.1f} | {r['p99']:.1f} | "
            f"{r['rps']:.0f} | {r['errors']} |"
        )


if __name__ == "__main__":
    asyncio.run(main())
