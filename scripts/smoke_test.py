#!/usr/bin/env python3
"""Smoke test — concurrent ingest + full WO lifecycle + MISMATCH loop + ledger chain.

Cases covered:
  [34] 10 concurrent reporters post simultaneously → no 500s, no deadlock
  [35] After concurrent ingest → flood_node.n_reports updated, /water-surface populated
  [G7] Corroboration gate → WO on 0-report node returns 422
  [WO] Happy path VERIFIED → create WO → confirm → verify VERIFIED → done
  [MISMATCH] Full MISMATCH loop → verify MISMATCH → escalate → confirm → VERIFIED
  [EDGE] State machine gates → 409 on wrong state, 422 on bad outcome literal
  [LEDGER] Chain integrity → SHA-256 hash-chain unbroken after all writes
  [CONCURRENT-LEDGER] Concurrent ledger writes → advisory lock prevents chain fork

Run: uv run --package api python scripts/smoke_test.py
Prerequisites: API server running (make api) + DB seeded (make seed)
"""

import asyncio
import hashlib
import json
import random
import sys
import textwrap
from dataclasses import dataclass, field

import httpx

API_URL = "http://localhost:8000"

REPORTERS = [
    {"handle": "smoke_00", "lat": 13.7465, "lon": 100.7770, "rough_level": "เข่า"},
    {"handle": "smoke_01", "lat": 13.7492, "lon": 100.7724, "rough_level": "เอว"},
    {"handle": "smoke_02", "lat": 13.7518, "lon": 100.7682, "rough_level": "ข้อเท้า"},
    {"handle": "smoke_03", "lat": 13.7443, "lon": 100.7698, "rough_level": "เข่า"},
    {"handle": "smoke_04", "lat": 13.7415, "lon": 100.7788, "rough_level": "ข้อเท้า"},
    {"handle": "smoke_05", "lat": 13.7602, "lon": 100.7544, "rough_level": "เอว"},
    {"handle": "smoke_06", "lat": 13.7312, "lon": 100.7852, "rough_level": "เข่า"},
    {"handle": "smoke_07", "lat": 13.7242, "lon": 100.7902, "rough_level": "อก"},
    {"handle": "smoke_08", "lat": 13.7183, "lon": 100.7682, "rough_level": "เอว"},
    {"handle": "smoke_09", "lat": 13.7382, "lon": 100.7592, "rough_level": "เข่า"},
]


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ReportResult:
    handle: str
    http_status: int
    status: str = ""
    water_level_m: float | None = None
    flood_node_id: int | None = None
    label: str = ""
    error: str = ""


@dataclass
class SmokeResult:
    reports: list[ReportResult] = field(default_factory=list)
    nodes_before: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    nodes_after: list[dict] = field(default_factory=list)   # type: ignore[type-arg]
    stats_after: dict = field(default_factory=dict)         # type: ignore[type-arg]
    surface_point_count: int = 0
    surface_level_range: tuple[float, float] = (0.0, 0.0)


# ── Formatting helpers ────────────────────────────────────────────────────────

def _ok(msg: str) -> str:
    return f"  \033[32m✓\033[0m {msg}"


def _fail(msg: str) -> str:
    return f"  \033[31m✗\033[0m {msg}"


def _info(msg: str) -> str:
    return f"  \033[90m·\033[0m {msg}"


def _skip(msg: str) -> str:
    return f"  \033[33m–\033[0m {msg}"


# ── Ledger chain verifier (mirrors AccountabilityBoard.tsx logic) ─────────────

def verify_chain(entries: list[dict]) -> tuple[bool, int | None]:  # type: ignore[type-arg]
    """Return (valid, broken_at_id). Uses same SHA-256 formula as services/ledger.py."""
    GENESIS = "0" * 64
    for idx, entry in enumerate(entries):
        raw = f"{entry['event_type']}|{entry['payload']}|{entry['prev_hash']}"
        computed = hashlib.sha256(raw.encode()).hexdigest()
        if computed != entry["hash"]:
            return False, entry["id"]
        expected_prev = GENESIS if idx == 0 else entries[idx - 1]["hash"]
        if entry["prev_hash"] != expected_prev:
            return False, entry["id"]
    return True, None


# ── Concurrent ingest helpers ─────────────────────────────────────────────────

async def post_report(client: httpx.AsyncClient, reporter: dict) -> ReportResult:  # type: ignore[type-arg]
    jlat = float(reporter["lat"]) + random.uniform(-0.0003, 0.0003)
    jlon = float(reporter["lon"]) + random.uniform(-0.0003, 0.0003)
    try:
        resp = await client.post(
            f"{API_URL}/ingest/report",
            data={
                "lat": str(jlat),
                "lon": str(jlon),
                "rough_level": reporter["rough_level"],
                "reporter_handle": reporter["handle"],
                "is_simulated": "true",
            },
            timeout=15.0,
        )
        if resp.status_code >= 500:
            return ReportResult(
                handle=reporter["handle"],
                http_status=resp.status_code,
                error=resp.text[:120],
            )
        data = resp.json()
        return ReportResult(
            handle=reporter["handle"],
            http_status=resp.status_code,
            status=data.get("status", ""),
            water_level_m=data.get("water_level_m"),
            flood_node_id=data.get("flood_node_id"),
            label=data.get("label", ""),
        )
    except Exception as exc:
        return ReportResult(handle=reporter["handle"], http_status=0, error=str(exc)[:120])


# ── Work-order helpers ────────────────────────────────────────────────────────

async def create_wo(client: httpx.AsyncClient, node_id: int) -> dict:  # type: ignore[type-arg]
    r = await client.post(
        f"{API_URL}/work-orders",
        json={"flood_node_id": node_id, "approved_by": "SmokeTest_Coordinator"},
        timeout=10.0,
    )
    return {"status_code": r.status_code, "body": r.json()}


async def confirm_wo(client: httpx.AsyncClient, wo_id: int, confirmed_by: str = "Smoke_Test") -> dict:  # type: ignore[type-arg]
    r = await client.post(
        f"{API_URL}/work-orders/{wo_id}/confirm",
        json={"confirmed_by": confirmed_by},
        timeout=10.0,
    )
    return {"status_code": r.status_code, "body": r.json()}


async def verify_wo(client: httpx.AsyncClient, wo_id: int, outcome: str, verified_by: str = "Smoke_Test") -> dict:  # type: ignore[type-arg]
    r = await client.post(
        f"{API_URL}/work-orders/{wo_id}/verify",
        json={"outcome": outcome, "verified_by": verified_by},
        timeout=10.0,
    )
    return {"status_code": r.status_code, "body": r.json()}


async def get_ledger(client: httpx.AsyncClient) -> list[dict]:  # type: ignore[type-arg]
    r = await client.get(f"{API_URL}/ledger", timeout=10.0)
    return r.json() if r.is_success else []


# ── Main run ──────────────────────────────────────────────────────────────────

async def run() -> SmokeResult:
    result = SmokeResult()
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/flood-nodes", timeout=10.0)
        result.nodes_before = r.json() if r.is_success else []

        result.reports = await asyncio.gather(
            *[post_report(client, rep) for rep in REPORTERS]
        )

        r = await client.get(f"{API_URL}/flood-nodes", timeout=10.0)
        result.nodes_after = r.json() if r.is_success else []

        r = await client.get(f"{API_URL}/stats", timeout=10.0)
        result.stats_after = r.json() if r.is_success else {}

        r = await client.get(f"{API_URL}/water-surface", timeout=10.0)
        if r.is_success:
            pts = r.json().get("points", [])
            result.surface_point_count = len(pts)
            if pts:
                levels = [p["level"] for p in pts]
                result.surface_level_range = (min(levels), max(levels))

    return result


# ── Print helpers for each group ──────────────────────────────────────────────

def check_34_35(res: SmokeResult) -> int:
    failures = 0

    print("\033[1m[34] 10 concurrent ingest reporters\033[0m")
    accepted = [r for r in res.reports if r.status == "accepted"]
    errors_5xx = [r for r in res.reports if r.http_status >= 500]
    conn_errors = [r for r in res.reports if r.http_status == 0]

    for r in res.reports:
        if r.error:
            print(_fail(f"{r.handle}: HTTP {r.http_status} — {r.error}"))
            failures += 1
        elif r.http_status >= 500:
            print(_fail(f"{r.handle}: HTTP {r.http_status}"))
            failures += 1
        else:
            lvl = f"{r.water_level_m:.2f}m" if r.water_level_m is not None else "None"
            print(
                _ok(f"{r.handle}: {r.status:10s}  level={lvl:6s}  "
                    f"node={str(r.flood_node_id):4s}  [{r.label}]")
            )

    if not errors_5xx and not conn_errors:
        print(_ok(f"No 500s or connection errors  ({len(accepted)}/{len(REPORTERS)} accepted)"))
    else:
        print(_fail(f"{len(errors_5xx)} × 500s, {len(conn_errors)} × connection errors"))
        failures += 1

    print()
    responded = [r for r in res.reports if r.http_status not in (0, 500)]
    simulated_labeled = [r for r in responded if r.label == "SIMULATED-by-design"]
    if len(simulated_labeled) == len(responded):
        print(_ok(f"G5: all {len(simulated_labeled)} responses labeled SIMULATED-by-design"))
    else:
        print(_fail(f"G5: {len(simulated_labeled)}/{len(responded)} labeled correctly"))
        failures += 1

    print(f"\n\033[1m[35] flood_node.n_reports updated after concurrent ingest\033[0m")
    before_map = {n["id"]: n for n in res.nodes_before}
    updated_nodes = []
    for node in res.nodes_after:
        nid = node["id"]
        before_n = before_map.get(nid, {}).get("n_reports", 0)
        after_n = node["n_reports"]
        if after_n > before_n:
            updated_nodes.append((node["name"], before_n, after_n, node["current_fused_level"]))

    if updated_nodes:
        for name, b, a, lvl in updated_nodes:
            lvl_str = f"{lvl:.3f}m" if lvl is not None else "None"
            print(_ok(f"{name}: n_reports {b}→{a},  fused_level={lvl_str}"))
    else:
        print(_fail("No nodes updated — check seed or node assignment radius"))
        failures += 1

    print(f"\n\033[1m/stats\033[0m")
    node_count = res.stats_after.get("flood_node_count", 0)
    reports_today = res.stats_after.get("reports_today", 0)
    if node_count > 0:
        print(_ok(f"flood_node_count = {node_count}"))
    else:
        print(_fail("flood_node_count = 0 (nodes not seeded?)"))
        failures += 1
    if reports_today > 0:
        print(_ok(f"reports_today    = {reports_today}"))
    else:
        print(_info("reports_today    = 0 (may be from a previous run — acceptable)"))

    print(f"\n\033[1m/water-surface\033[0m")
    if res.surface_point_count == 625:
        lo, hi = res.surface_level_range
        print(_ok("625 grid points returned (25×25)"))
        print(_ok(f"level range: {lo:.3f}m – {hi:.3f}m"))
    elif res.surface_point_count == 0:
        print(_info("0 points — < 2 nodes with fused_level (run make seed first)"))
    else:
        print(_fail(f"Expected 625 points, got {res.surface_point_count}"))
        failures += 1

    return failures


async def check_g7(client: httpx.AsyncClient, nodes_after: list[dict]) -> int:  # type: ignore[type-arg]
    print(f"\n\033[1m[G7] Corroboration gate\033[0m")
    zero_nodes = [n for n in nodes_after if (n.get("n_reports") or 0) == 0]
    if not zero_nodes:
        print(_skip("All nodes have n_reports ≥ 1 after ingest — G7 gate cannot be tested on fresh node"))
        print(_info("G7 is enforced in code (see routers/work_orders.py); run make seed to reset"))
        return 0

    node_id = zero_nodes[0]["id"]
    r = await client.post(
        f"{API_URL}/work-orders",
        json={"flood_node_id": node_id, "approved_by": "SmokeTest_Coordinator"},
        timeout=10.0,
    )
    if r.status_code == 422 and "G7" in r.text:
        print(_ok(f"WO on node {node_id} (n_reports=0) → 422 G7 rejected"))
        return 0
    else:
        print(_fail(f"Expected 422 G7, got HTTP {r.status_code}: {r.text[:80]}"))
        return 1


async def check_wo_happy_path(client: httpx.AsyncClient, nodes_after: list[dict]) -> tuple[int, int | None]:  # type: ignore[type-arg]
    """Returns (failures, node_id_used) — node_id_used for reuse in MISMATCH test."""
    print(f"\n\033[1m[WO] Work order happy path (VERIFIED)\033[0m")
    failures = 0

    active = [
        n for n in nodes_after
        if (n.get("n_reports") or 0) >= 1 and n.get("current_fused_level") is not None
    ]
    if not active:
        print(_skip("No active node (n_reports ≥ 1 + fused_level) — skipping [WO] and [MISMATCH]"))
        return 0, None

    node_id = active[0]["id"]
    node_name = active[0]["name"]

    # Create
    res = await create_wo(client, node_id)
    if res["status_code"] != 201:
        print(_fail(f"POST /work-orders → {res['status_code']}: {str(res['body'])[:80]}"))
        return 1, None
    wo_id: int = res["body"]["id"]
    print(_ok(f"POST /work-orders on '{node_name}' → id={wo_id} status=pending"))

    # Confirm
    res = await confirm_wo(client, wo_id)
    if res["status_code"] != 200 or res["body"].get("status") != "dispatched":
        print(_fail(f"POST /confirm → {res['status_code']} status={res['body'].get('status')}"))
        failures += 1
    else:
        print(_ok(f"POST /confirm → status=dispatched"))

    # Verify VERIFIED
    res = await verify_wo(client, wo_id, "VERIFIED")
    if res["status_code"] != 201:
        print(_fail(f"POST /verify VERIFIED → {res['status_code']}: {str(res['body'])[:80]}"))
        failures += 1
    elif res["body"].get("new_work_order_id") is not None:
        print(_fail(f"VERIFIED should have new_work_order_id=null, got {res['body']['new_work_order_id']}"))
        failures += 1
    else:
        print(_ok("POST /verify VERIFIED → 201 new_work_order_id=null"))

    # Ledger check — WO_CREATED + WO_DISPATCHED + VERIFY_OUTCOME present
    ledger = await get_ledger(client)
    types = {e["event_type"] for e in ledger}
    for expected in ("WO_CREATED", "WO_DISPATCHED", "VERIFY_OUTCOME"):
        if expected in types:
            print(_ok(f"Ledger has {expected}"))
        else:
            print(_fail(f"Ledger missing {expected}"))
            failures += 1

    return failures, node_id


async def check_mismatch(client: httpx.AsyncClient, node_id: int | None) -> int:
    print(f"\n\033[1m[MISMATCH] Full MISMATCH loop\033[0m")
    if node_id is None:
        print(_skip("No active node available — skipping (see [WO] skip above)"))
        return 0

    failures = 0

    # Create + confirm WO
    res = await create_wo(client, node_id)
    if res["status_code"] != 201:
        print(_fail(f"POST /work-orders → {res['status_code']}"))
        return 1
    wo_id: int = res["body"]["id"]
    print(_ok(f"POST /work-orders → id={wo_id}"))

    res = await confirm_wo(client, wo_id)
    if res["status_code"] != 200:
        print(_fail(f"POST /confirm → {res['status_code']}"))
        return 1
    print(_ok("POST /confirm → dispatched"))

    # Verify MISMATCH
    res = await verify_wo(client, wo_id, "MISMATCH")
    if res["status_code"] != 201:
        print(_fail(f"POST /verify MISMATCH → {res['status_code']}: {str(res['body'])[:80]}"))
        return 1
    new_wo_id: int | None = res["body"].get("new_work_order_id")
    if new_wo_id is None:
        print(_fail("MISMATCH → new_work_order_id should not be null"))
        return 1
    print(_ok(f"POST /verify MISMATCH → new_work_order_id={new_wo_id}"))

    # Ledger must have MISMATCH_ESCALATE
    ledger = await get_ledger(client)
    has_escalate = any(e["event_type"] == "MISMATCH_ESCALATE" for e in ledger)
    if has_escalate:
        print(_ok("Ledger has MISMATCH_ESCALATE"))
    else:
        print(_fail("Ledger missing MISMATCH_ESCALATE"))
        failures += 1

    # Escalated WO should be pending
    r = await client.get(f"{API_URL}/work-orders?status=pending", timeout=10.0)
    if r.is_success:
        pending_ids = [w["id"] for w in r.json()]
        if new_wo_id in pending_ids:
            print(_ok(f"Escalated WO#{new_wo_id} status=pending"))
        else:
            print(_fail(f"Escalated WO#{new_wo_id} not in pending list"))
            failures += 1

    # Close the loop: confirm + VERIFIED on escalated WO
    res = await confirm_wo(client, new_wo_id)
    if res["status_code"] != 200:
        print(_fail(f"Confirm escalated WO#{new_wo_id} → {res['status_code']}"))
        failures += 1
    else:
        print(_ok(f"Confirm escalated WO#{new_wo_id} → dispatched"))

    res = await verify_wo(client, new_wo_id, "VERIFIED", verified_by="Smoke_Test_Citizen")
    if res["status_code"] != 201 or res["body"].get("new_work_order_id") is not None:
        print(_fail(f"Verify VERIFIED on escalated WO → {res['status_code']} / new_wo={res['body'].get('new_work_order_id')}"))
        failures += 1
    else:
        print(_ok(f"Verify escalated WO#{new_wo_id} VERIFIED → done, loop closed"))

    # Verify full sequence in ledger
    ledger = await get_ledger(client)
    relevant = [
        e for e in ledger
        if e["event_type"] in ("WO_CREATED", "WO_DISPATCHED", "VERIFY_OUTCOME", "MISMATCH_ESCALATE")
    ]
    type_seq = [e["event_type"] for e in relevant]
    has_full = (
        "WO_CREATED" in type_seq
        and "WO_DISPATCHED" in type_seq
        and "VERIFY_OUTCOME" in type_seq
        and "MISMATCH_ESCALATE" in type_seq
    )
    if has_full:
        print(_ok(f"Full lifecycle in ledger: {' → '.join(dict.fromkeys(type_seq))}"))
    else:
        print(_fail(f"Incomplete lifecycle in ledger: {type_seq}"))
        failures += 1

    return failures


async def check_edge_cases(client: httpx.AsyncClient, nodes_after: list[dict]) -> int:  # type: ignore[type-arg]
    print(f"\n\033[1m[EDGE] State machine gates\033[0m")
    failures = 0

    # Need an active node for WO creation
    active = [
        n for n in nodes_after
        if (n.get("n_reports") or 0) >= 1 and n.get("current_fused_level") is not None
    ]
    if not active:
        print(_skip("No active node — skipping edge case WO tests"))
        return 0

    node_id = active[0]["id"]

    # Create + confirm a WO, then try to confirm again (should 409)
    res = await create_wo(client, node_id)
    if res["status_code"] != 201:
        print(_fail(f"Setup: POST /work-orders → {res['status_code']}"))
        return 1
    wo_id: int = res["body"]["id"]

    # Edge 1: verify on pending WO (not dispatched yet) → 409
    res = await verify_wo(client, wo_id, "VERIFIED")
    if res["status_code"] == 409:
        print(_ok("Verify on pending WO → 409 (expected 'dispatched')"))
    else:
        print(_fail(f"Verify on pending WO → {res['status_code']} (expected 409)"))
        failures += 1

    # Now confirm it
    await confirm_wo(client, wo_id)

    # Edge 2: confirm on dispatched WO → 409
    res = await confirm_wo(client, wo_id)
    if res["status_code"] == 409:
        print(_ok("Confirm on dispatched WO → 409 (expected 'pending')"))
    else:
        print(_fail(f"Confirm on dispatched WO → {res['status_code']} (expected 409)"))
        failures += 1

    # Edge 3: lowercase outcome → 422 (Pydantic Literal gate)
    res = await verify_wo(client, wo_id, "mismatch")
    if res["status_code"] == 422:
        print(_ok("outcome='mismatch' (lowercase) → 422 Pydantic Literal rejected"))
    else:
        print(_fail(f"outcome='mismatch' → {res['status_code']} (expected 422)"))
        failures += 1

    # Clean up: verify it as VERIFIED so it doesn't pollute later chain test
    await verify_wo(client, wo_id, "VERIFIED")

    return failures


async def check_ledger_chain(client: httpx.AsyncClient) -> int:
    print(f"\n\033[1m[LEDGER] Chain integrity\033[0m")
    ledger = await get_ledger(client)

    if not ledger:
        print(_fail("Ledger is empty — no events recorded"))
        return 1

    valid, broken_at = verify_chain(ledger)
    event_types = {}
    for e in ledger:
        event_types[e["event_type"]] = event_types.get(e["event_type"], 0) + 1

    if valid:
        print(_ok(f"{len(ledger)} entries — all SHA-256 hashes valid"))
        print(_ok(f"prev_hash links unbroken (genesis → #{ledger[-1]['id']})"))
    else:
        print(_fail(f"Chain broken at entry #{broken_at}"))
        return 1

    for etype, count in sorted(event_types.items()):
        print(_info(f"{etype}: {count} event(s)"))

    # All entries should be labeled
    unlabeled = [e for e in ledger if not e.get("data_class")]
    if unlabeled:
        print(_fail(f"G9: {len(unlabeled)} entries missing data_class label"))
        return 1
    print(_ok(f"G9: all {len(ledger)} entries carry data_class label"))

    return 0


async def check_concurrent_ledger(client: httpx.AsyncClient, nodes_after: list[dict]) -> int:  # type: ignore[type-arg]
    print(f"\n\033[1m[CONCURRENT-LEDGER] Concurrent ledger writes\033[0m")

    active = [
        n for n in nodes_after
        if (n.get("n_reports") or 0) >= 1 and n.get("current_fused_level") is not None
    ]
    if len(active) < 2:
        print(_skip(f"Need ≥ 2 active nodes, have {len(active)} — skipping"))
        return 0

    failures = 0

    # Create 2 WOs on different nodes
    res_a, res_b = await asyncio.gather(
        create_wo(client, active[0]["id"]),
        create_wo(client, active[1]["id"]),
    )
    if res_a["status_code"] != 201 or res_b["status_code"] != 201:
        print(_fail(f"WO creation: {res_a['status_code']} / {res_b['status_code']}"))
        return 1
    wo_a: int = res_a["body"]["id"]
    wo_b: int = res_b["body"]["id"]
    print(_ok(f"Created WO#{wo_a} and WO#{wo_b} on two nodes"))

    # Confirm both simultaneously — two WO_DISPATCHED events hit ledger concurrently
    conf_a, conf_b = await asyncio.gather(
        confirm_wo(client, wo_a, "Smoke_Concurrent_A"),
        confirm_wo(client, wo_b, "Smoke_Concurrent_B"),
    )
    if conf_a["status_code"] != 200 or conf_b["status_code"] != 200:
        print(_fail(f"Confirm: {conf_a['status_code']} / {conf_b['status_code']}"))
        failures += 1
    else:
        print(_ok("Confirmed both WOs concurrently — no 500s"))

    # Verify both simultaneously — two VERIFY_OUTCOME events hit ledger concurrently
    ver_a, ver_b = await asyncio.gather(
        verify_wo(client, wo_a, "VERIFIED", "Concurrent_Citizen_A"),
        verify_wo(client, wo_b, "VERIFIED", "Concurrent_Citizen_B"),
    )
    if ver_a["status_code"] != 201 or ver_b["status_code"] != 201:
        print(_fail(f"Verify: {ver_a['status_code']} / {ver_b['status_code']}"))
        failures += 1
    else:
        print(_ok("Verified both WOs concurrently — no 500s"))

    # Chain must still be valid after concurrent writes
    ledger = await get_ledger(client)
    valid, broken_at = verify_chain(ledger)
    if valid:
        print(_ok(f"Chain intact after concurrent writes ({len(ledger)} total entries)"))
    else:
        print(_fail(f"Chain forked at entry #{broken_at} — advisory lock may have failed"))
        failures += 1

    return failures


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    print(textwrap.dedent(f"""\
        Smoke test → {API_URL}
        Reporters : {len(REPORTERS)} concurrent (is_simulated=true)
    """))

    try:
        async with httpx.AsyncClient() as c:
            h = await c.get(f"{API_URL}/health", timeout=5.0)
            h.raise_for_status()
    except Exception as exc:
        print(f"\033[31mAPI not reachable: {exc}\033[0m")
        print("Run: uv run --package api fastapi dev apps/api/src/api/main.py")
        sys.exit(1)

    result = await run()
    total_failures = 0

    print("\n\033[1m══ Floodtir Smoke Test ══\033[0m\n")

    total_failures += check_34_35(result)

    async with httpx.AsyncClient() as client:
        total_failures += await check_g7(client, result.nodes_after)
        f_wo, node_id_used = await check_wo_happy_path(client, result.nodes_after)
        total_failures += f_wo
        total_failures += await check_mismatch(client, node_id_used)
        total_failures += await check_edge_cases(client, result.nodes_after)
        total_failures += await check_ledger_chain(client)
        total_failures += await check_concurrent_ledger(client, result.nodes_after)

    print()
    if total_failures == 0:
        print("\033[32m\033[1m✓ All smoke checks passed\033[0m\n")
    else:
        print(f"\033[31m\033[1m✗ {total_failures} check(s) failed\033[0m\n")

    sys.exit(total_failures)


if __name__ == "__main__":
    asyncio.run(main())
