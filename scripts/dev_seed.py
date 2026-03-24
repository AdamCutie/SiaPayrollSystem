from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure imports work when running as a script (python .\scripts\dev_seed.py ...)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import check_db_connection, close_db_connection, db
from integrations.hr.adapter import get_all_active_employees


TARGET_COLLECTIONS: tuple[str, ...] = (
    "Holidays",
    "PayrollConfigOverrides",
    "LeaveRequests",
    "AttendanceLogs",
    "PenaltyRecords",
    "OvertimeRecords",
    "PayrollSnapshots",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _count_weekdays(start_date: datetime, end_date: datetime) -> int:
    start_day = start_date.date()
    end_day = end_date.date()
    if end_day < start_day:
        return 0
    days = 0
    cursor = start_day
    while cursor <= end_day:
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return days


@dataclass(frozen=True)
class SeedEmployee:
    employee_id: str
    employee_number: str
    full_name: str
    department: str
    position: str


def _build_seed_employees(employees) -> list[SeedEmployee]:
    seed_employees: list[SeedEmployee] = []
    for employee in employees:
        seed_employees.append(
            SeedEmployee(
                employee_id=employee.id,
                employee_number=employee.employeeId,
                full_name=f"{employee.lastName}, {employee.firstName}",
                department=employee.department or "Unassigned",
                position="Staff",
            )
        )
    return seed_employees


async def clear_seed(tag: str) -> None:
    for name in TARGET_COLLECTIONS:
        result = await db[name].delete_many({"seed_tag": tag})
        print(f"{name}: deleted {result.deleted_count}")


async def seed_payroll_db(tag: str, employees_limit: int, *, include_snapshots: bool) -> int:
    ok = await check_db_connection()
    if not ok:
        print("ERROR: Cannot connect to MongoDB. Check your .env MONGODB_URL.")
        return 1

    hr_employees = await get_all_active_employees(limit=employees_limit)
    if not hr_employees:
        print("ERROR: No active HR employees found. Cannot seed without HR identities.")
        return 1

    seed_employees = _build_seed_employees(hr_employees)

    # Make seeding idempotent for the same tag
    print(f"Clearing existing seed docs (tag={tag})...")
    await clear_seed(tag)

    now = _utc_now()

    # --- Holidays (ensure there is an upcoming one) ---
    holidays = [
        {
            "date": now + timedelta(days=7),
            "name": "Seed Holiday (Upcoming)",
            "type": "Regular Holiday",
            "seed_tag": tag,
        },
        {
            "date": now + timedelta(days=30),
            "name": "Seed Holiday (Next Month)",
            "type": "Special Non-Working Day",
            "seed_tag": tag,
        },
        {
            "date": now - timedelta(days=30),
            "name": "Seed Holiday (Past)",
            "type": "Regular Holiday",
            "seed_tag": tag,
        },
    ]
    await db["Holidays"].insert_many(holidays)
    print(f"Holidays: inserted {len(holidays)}")

    # --- Common pay period for seeded snapshots ---
    period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    period_end = period_start + timedelta(days=14)
    expected_workdays = _count_weekdays(period_start, period_end)

    # --- Per-employee docs ---
    payroll_config_docs = []
    leave_docs = []
    attendance_docs = []
    penalty_docs = []
    overtime_docs = []
    snapshot_docs = []

    for idx, employee in enumerate(seed_employees):
        # Leaves (create approved + pending + rejected, mix paid/unpaid)
        leave_docs.extend(
            [
                {
                    "employee_id": employee.employee_id,
                    "employee_number": employee.employee_number,
                    "full_name": employee.full_name,
                    "leave_type": "Vacation",
                    "start_date": now - timedelta(days=20),
                    "end_date": now - timedelta(days=18),
                    "status": "Approved",
                    "is_paid": True,
                    "seed_tag": tag,
                },
                {
                    "employee_id": employee.employee_id,
                    "employee_number": employee.employee_number,
                    "full_name": employee.full_name,
                    "leave_type": "Sick",
                    "start_date": now - timedelta(days=10),
                    "end_date": now - timedelta(days=10),
                    "status": "Approved",
                    "is_paid": False,
                    "seed_tag": tag,
                },
                {
                    "employee_id": employee.employee_id,
                    "employee_number": employee.employee_number,
                    "full_name": employee.full_name,
                    "leave_type": "Sick",
                    "start_date": now + timedelta(days=3),
                    "end_date": now + timedelta(days=3),
                    "status": "Pending",
                    "is_paid": True,
                    "seed_tag": tag,
                },
                {
                    "employee_id": employee.employee_id,
                    "employee_number": employee.employee_number,
                    "full_name": employee.full_name,
                    "leave_type": "Vacation",
                    "start_date": now - timedelta(days=40),
                    "end_date": now - timedelta(days=39),
                    "status": "Rejected",
                    "is_paid": True,
                    "seed_tag": tag,
                },
            ]
        )

        # Attendance logs (create a few with different statuses)
        statuses = ["Pending", "Approved", "Rejected"]
        for d in range(1, 7):
            attendance_docs.append(
                {
                    "employee_id": employee.employee_id,
                    "employee_number": employee.employee_number,
                    "full_name": employee.full_name,
                    "department": employee.department,
                    "position": employee.position,
                    "date": now - timedelta(days=d),
                    "duration_hours": 8.0,
                    "status": statuses[d % len(statuses)],
                    "seed_tag": tag,
                }
            )

        # Penalties / Overtime (to exercise net-pay adjustments + approvals counts)
        penalty_docs.append(
            {
                "employee_id": employee.employee_id,
                "full_name": employee.full_name,
                "date": now - timedelta(days=5),
                "penalty_type": "Tardiness",
                "amount": 200.0 + (idx * 25.0),
                "status": "Approved",
                "seed_tag": tag,
            }
        )
        overtime_docs.append(
            {
                "employee_id": employee.employee_id,
                "full_name": employee.full_name,
                "date": now - timedelta(days=6),
                "hours": 2.0,
                "rate_per_hour": 150.0,
                "total_pay": 300.0,
                "status": "Approved",
                "seed_tag": tag,
            }
        )

        # Payroll snapshot (so /overview, /history, /csv have data)
        basic_salary = 30000.0 + (idx * 1000.0)
        gross_pay = basic_salary + 2000.0
        total_deductions = 1500.0
        net_pay = (gross_pay + 300.0) - (total_deductions + (200.0 + (idx * 25.0)))

        # Payroll config overrides (stored in the payroll DB; HR DB remains read-only)
        payroll_config_docs.append(
            {
                "employeeId": employee.employee_id,
                "employeeNumber": employee.employee_number,
                "employeeName": employee.full_name,
                "basicSalary": basic_salary,
                "housingAllowance": 1000.0,
                "transportAllowance": 500.0,
                "mealAllowance": 500.0,
                "otherAllowances": 0.0,
                "sssContribution": 0.0,
                "philHealthContribution": 0.0,
                "pagIbigContribution": 0.0,
                "withholdingTax": 0.0,
                "sssLoan": 0.0,
                "pagIbigLoan": 0.0,
                "companyLoan": 0.0,
                "absencePenaltyRate": 0.0,
                "latePenaltyRate": 0.0,
                "updatedAt": now,
                "seed_tag": tag,
            }
        )

        snapshot_docs.append(
            {
                "employee_id": employee.employee_id,
                "employee_number": employee.employee_number,
                "full_name": employee.full_name,
                "department": employee.department,
                "basic_salary": basic_salary,
                "gross_pay": gross_pay,
                "total_deductions": total_deductions,
                "net_pay": round(max(0.0, net_pay), 2),
                "days_worked": expected_workdays,
                "days_present": max(0, expected_workdays - 1),
                "days_absent": 1 if expected_workdays > 0 else 0,
                "pay_period_start": period_start,
                "pay_period_end": period_end,
                "processed_at": now - timedelta(days=1),
                "status": "Delayed" if idx == 0 else "Completed",
                "seed_tag": tag,
            }
        )

    await db["PayrollConfigOverrides"].insert_many(payroll_config_docs)
    await db["LeaveRequests"].insert_many(leave_docs)
    await db["AttendanceLogs"].insert_many(attendance_docs)
    await db["PenaltyRecords"].insert_many(penalty_docs)
    await db["OvertimeRecords"].insert_many(overtime_docs)
    if include_snapshots:
        await db["PayrollSnapshots"].insert_many(snapshot_docs)

    print(f"PayrollConfigOverrides: inserted {len(payroll_config_docs)}")
    print(f"LeaveRequests: inserted {len(leave_docs)}")
    print(f"AttendanceLogs: inserted {len(attendance_docs)}")
    print(f"PenaltyRecords: inserted {len(penalty_docs)}")
    print(f"OvertimeRecords: inserted {len(overtime_docs)}")
    if include_snapshots:
        print(f"PayrollSnapshots: inserted {len(snapshot_docs)}")

    print("Seed complete.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed/clear dev data for SiaPayrollSystem (payroll DB only).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    seed = sub.add_parser("seed", help="Insert dev seed data into payroll DB (tagged for cleanup).")
    seed.add_argument("--tag", default="dev-seed", help="Seed tag used to mark inserted docs.")
    seed.add_argument("--employees-limit", type=int, default=5, help="How many active HR employees to seed against.")
    seed.add_argument(
        "--no-snapshots",
        action="store_true",
        help="Do not pre-insert PayrollSnapshots (useful when you want /processing/run to generate them).",
    )

    clear = sub.add_parser("clear", help="Delete previously seeded dev data by tag.")
    clear.add_argument("--tag", default="dev-seed", help="Seed tag used to mark inserted docs.")

    return parser


async def _run() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.cmd == "seed":
            return await seed_payroll_db(
                tag=args.tag,
                employees_limit=args.employees_limit,
                include_snapshots=not args.no_snapshots,
            )
        if args.cmd == "clear":
            await clear_seed(tag=args.tag)
            return 0
        raise ValueError(f"Unknown command: {args.cmd}")
    finally:
        close_db_connection()


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
