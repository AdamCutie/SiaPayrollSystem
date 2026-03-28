from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Ensure imports work when running as a script (python .\scripts\dev_cleanup.py ...)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import check_db_connection, close_db_connection, db


def _parse_iso_datetime(value: str) -> datetime:
    raw = value.strip()
    # Support common "Z" suffix
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Invalid datetime '{value}'. Use ISO like 2026-03-01T00:00:00 or 2026-03-01T00:00:00+08:00."
        ) from e


def _require_delete_confirmation(apply: bool, confirm: str | None) -> None:
    if not apply:
        return
    if confirm != "DELETE":
        raise SystemExit("Refusing to delete. Re-run with --confirm DELETE")


async def snapshots_report_dupes(
    *,
    start_date: datetime | None,
    end_date: datetime | None,
    limit: int,
) -> int:
    ok = await check_db_connection()
    if not ok:
        print("ERROR: Cannot connect to MongoDB. Check your .env MONGODB_URL.")
        return 1

    match_stage = {}
    if (start_date is None) ^ (end_date is None):
        print("ERROR: Provide both --start-date and --end-date, or neither.")
        return 2
    if start_date is not None and end_date is not None:
        match_stage = {"pay_period_start": start_date, "pay_period_end": end_date}

    pipeline: list[dict] = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend(
        [
            {
                "$group": {
                    "_id": {
                        "employee_id": "$employee_id",
                        "pay_period_start": "$pay_period_start",
                        "pay_period_end": "$pay_period_end",
                    },
                    "count": {"$sum": 1},
                    "full_name": {"$first": "$full_name"},
                    "employee_number": {"$first": "$employee_number"},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": int(limit)},
        ]
    )

    cursor = db["PayrollSnapshots"].aggregate(pipeline, allowDiskUse=True)
    dupes = [doc async for doc in cursor]

    if not dupes:
        print("No duplicate snapshot groups found.")
        return 0

    print(f"Duplicate snapshot groups (showing up to {limit}):")
    for idx, d in enumerate(dupes, 1):
        group = d["_id"]
        start = group["pay_period_start"]
        end = group["pay_period_end"]
        print(
            f"{idx}. {d.get('full_name','<unknown>')} ({d.get('employee_number','?')}) "
            f"employee_id={group['employee_id']} period={start}..{end} count={d['count']}"
        )

    print("")
    print("Next:")
    print("  - To dedupe a specific period, run:")
    print("    python .\\scripts\\dev_cleanup.py snapshots-dedupe --start-date <...> --end-date <...>")
    return 0


async def snapshots_dedupe(
    *,
    start_date: datetime | None,
    end_date: datetime | None,
    keep: str,
    apply: bool,
    confirm: str | None,
    max_groups: int,
) -> int:
    _require_delete_confirmation(apply, confirm)

    ok = await check_db_connection()
    if not ok:
        print("ERROR: Cannot connect to MongoDB. Check your .env MONGODB_URL.")
        return 1

    if (start_date is None) ^ (end_date is None):
        print("ERROR: Provide both --start-date and --end-date, or neither.")
        return 2

    match_stage = {}
    if start_date is not None and end_date is not None:
        match_stage = {"pay_period_start": start_date, "pay_period_end": end_date}

    pipeline: list[dict] = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend(
        [
            {
                "$group": {
                    "_id": {
                        "employee_id": "$employee_id",
                        "pay_period_start": "$pay_period_start",
                        "pay_period_end": "$pay_period_end",
                    },
                    "count": {"$sum": 1},
                    "full_name": {"$first": "$full_name"},
                    "employee_number": {"$first": "$employee_number"},
                    "snapshot_ids": {"$push": "$_id"},
                    "processed_ats": {"$push": "$processed_at"},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": int(max_groups)},
        ]
    )

    groups = [doc async for doc in db["PayrollSnapshots"].aggregate(pipeline, allowDiskUse=True)]
    if not groups:
        print("No duplicate snapshot groups found.")
        return 0

    total_to_delete = 0
    delete_ops: list[list] = []

    def sort_key(ts: datetime | None) -> datetime:
        return ts or datetime.min

    for g in groups:
        ids = g["snapshot_ids"]
        ats = g["processed_ats"]
        pairs = list(zip(ids, ats))
        pairs.sort(key=lambda p: sort_key(p[1]), reverse=(keep == "newest"))

        keep_id = pairs[0][0]
        to_delete = [pid for pid, _ in pairs[1:]]
        if not to_delete:
            continue
        total_to_delete += len(to_delete)
        delete_ops.append(to_delete)

        group = g["_id"]
        print(
            f"{g.get('full_name','<unknown>')} ({g.get('employee_number','?')}) "
            f"employee_id={group['employee_id']} period={group['pay_period_start']}..{group['pay_period_end']} "
            f"keep={keep_id} delete_count={len(to_delete)}"
        )

    print("")
    if not apply:
        print(f"Dry-run only. Would delete {total_to_delete} duplicate snapshots across {len(delete_ops)} groups.")
        print("Re-run with: --apply --confirm DELETE")
        return 0

    deleted = 0
    for ids in delete_ops:
        result = await db["PayrollSnapshots"].delete_many({"_id": {"$in": ids}})
        deleted += result.deleted_count

    print(f"Deleted {deleted} duplicate snapshots.")
    return 0


async def snapshots_delete_period(
    *,
    start_date: datetime,
    end_date: datetime,
    employee_id: str | None,
    apply: bool,
    confirm: str | None,
) -> int:
    _require_delete_confirmation(apply, confirm)

    ok = await check_db_connection()
    if not ok:
        print("ERROR: Cannot connect to MongoDB. Check your .env MONGODB_URL.")
        return 1

    query: dict = {"pay_period_start": start_date, "pay_period_end": end_date}
    if employee_id:
        query["employee_id"] = employee_id

    count = await db["PayrollSnapshots"].count_documents(query)
    print(f"Matched {count} snapshots for deletion.")

    if not apply:
        print("Dry-run only. Re-run with: --apply --confirm DELETE")
        return 0

    result = await db["PayrollSnapshots"].delete_many(query)
    print(f"Deleted {result.deleted_count} snapshots.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dev-safe cleanup utilities (payroll DB).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    report = sub.add_parser("snapshots-report-dupes", help="Report duplicate PayrollSnapshots groups.")
    report.add_argument("--start-date", type=_parse_iso_datetime, help="Pay period start ISO datetime.")
    report.add_argument("--end-date", type=_parse_iso_datetime, help="Pay period end ISO datetime.")
    report.add_argument("--limit", type=int, default=25, help="Max groups to show.")

    dedupe = sub.add_parser("snapshots-dedupe", help="Delete duplicate PayrollSnapshots while keeping one per group.")
    dedupe.add_argument("--start-date", type=_parse_iso_datetime, help="Pay period start ISO datetime.")
    dedupe.add_argument("--end-date", type=_parse_iso_datetime, help="Pay period end ISO datetime.")
    dedupe.add_argument("--keep", choices=["newest", "oldest"], default="newest", help="Which snapshot to keep.")
    dedupe.add_argument("--max-groups", type=int, default=500, help="Max duplicate groups to process.")
    dedupe.add_argument("--apply", action="store_true", help="Actually delete duplicates (otherwise dry-run).")
    dedupe.add_argument("--confirm", help='Type DELETE to confirm deletion (required with --apply).')

    delete_period = sub.add_parser("snapshots-delete-period", help="Delete snapshots for a specific pay period.")
    delete_period.add_argument("--start-date", type=_parse_iso_datetime, required=True, help="Pay period start ISO datetime.")
    delete_period.add_argument("--end-date", type=_parse_iso_datetime, required=True, help="Pay period end ISO datetime.")
    delete_period.add_argument("--employee-id", help="Optional: limit deletion to one employee_id.")
    delete_period.add_argument("--apply", action="store_true", help="Actually delete (otherwise dry-run).")
    delete_period.add_argument("--confirm", help='Type DELETE to confirm deletion (required with --apply).')

    return parser


async def _run() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.cmd == "snapshots-report-dupes":
            return await snapshots_report_dupes(
                start_date=args.start_date,
                end_date=args.end_date,
                limit=args.limit,
            )
        if args.cmd == "snapshots-dedupe":
            return await snapshots_dedupe(
                start_date=args.start_date,
                end_date=args.end_date,
                keep=args.keep,
                apply=args.apply,
                confirm=args.confirm,
                max_groups=args.max_groups,
            )
        if args.cmd == "snapshots-delete-period":
            return await snapshots_delete_period(
                start_date=args.start_date,
                end_date=args.end_date,
                employee_id=args.employee_id,
                apply=args.apply,
                confirm=args.confirm,
            )
        raise ValueError(f"Unknown command: {args.cmd}")
    finally:
        close_db_connection()


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()

