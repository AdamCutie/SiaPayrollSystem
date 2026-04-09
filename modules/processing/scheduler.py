import asyncio
import calendar
from datetime import datetime, timedelta
from typing import List, Optional, Any
from core.database import db
from db.models import PayrollSchedule
from .service import PayrollProcessingService

class PayrollSchedulerService:
    """
    Handles the automation of the 2026 Payroll Schedule.
    """
    _task: Optional[asyncio.Task] = None
    _stop_event: Optional[asyncio.Event] = None

    @classmethod
    async def _automation_loop(cls):
        """Background loop that checks for cutoffs."""
        assert cls._stop_event is not None
        while not cls._stop_event.is_set():
            try:
                # Run the check
                await cls.check_and_run_automated_payroll()
            except Exception as e:
                print(f"[ERROR] Automated Payroll Runner: {str(e)}")

            # Wait for 1 hour before checking again
            try:
                await asyncio.wait_for(cls._stop_event.wait(), timeout=3600)
            except asyncio.TimeoutError:
                continue

    @classmethod
    async def start_automation_runner(cls):
        if cls._task is not None:
            return
        cls._stop_event = asyncio.Event()
        cls._task = asyncio.create_task(cls._automation_loop())
        print("[OK] Automated Payroll Runner: STARTED.")

    @classmethod
    async def stop_automation_runner(cls):
        if cls._task is None:
            return
        assert cls._stop_event is not None
        cls._stop_event.set()
        try:
            await cls._task
        finally:
            cls._task = None
            cls._stop_event = None
            print("[OK] Automated Payroll Runner: STOPPED.")

    @staticmethod
    async def get_holidays():
        cursor = db['Holidays'].find({})
        hols = await cursor.to_list(None)
        return {h['date'].date() if isinstance(h['date'], datetime) else datetime.fromisoformat(h['date'].split('T')[0]).date() for h in hols}

    @staticmethod
    def adjust_to_previous_working_day(target_date, holiday_dates):
        while target_date.weekday() == 6 or target_date in holiday_dates:
            target_date -= timedelta(days=1)
        return target_date

    @classmethod
    async def generate_full_year_schedule(cls, year: int, automation_on: bool = False):
        """
        Calculates and saves the 24 cycles for the given year to the database.
        """
        collection = db["PayrollSchedules"]
        # Clear existing for that year to avoid duplicates
        await collection.delete_many({"year": year})
        
        holiday_dates = await cls.get_holidays()
        schedules = []

        for month in range(1, 13):
            # --- FIRST HALF ---
            start1 = datetime(year, month, 1)
            end1 = datetime(year, month, 13)
            cutoff1 = cls.adjust_to_previous_working_day(end1.date(), holiday_dates)
            payday1 = cls.adjust_to_previous_working_day(datetime(year, month, 15).date(), holiday_dates)
            
            schedules.append(PayrollSchedule(
                year=year,
                cycle_name=f"{calendar.month_name[month]} - First Half",
                period_start=start1,
                period_end=end1.replace(hour=23, minute=59, second=59),
                cutoff_date=datetime.combine(cutoff1, datetime.min.time()),
                pay_date=datetime.combine(payday1, datetime.min.time()),
                automation_on=automation_on
            ))

            # --- SECOND HALF ---
            start2 = datetime(year, month, 14)
            last_day = calendar.monthrange(year, month)[1]
            end2 = datetime(year, month, 28)
            cutoff2 = cls.adjust_to_previous_working_day(end2.date(), holiday_dates)
            payday2 = cls.adjust_to_previous_working_day(datetime(year, month, last_day).date(), holiday_dates)

            schedules.append(PayrollSchedule(
                year=year,
                cycle_name=f"{calendar.month_name[month]} - Second Half",
                period_start=start2,
                period_end=end2.replace(hour=23, minute=59, second=59),
                cutoff_date=datetime.combine(cutoff2, datetime.min.time()),
                pay_date=datetime.combine(payday2, datetime.min.time()),
                automation_on=automation_on
            ))

        # Insert all into DB
        docs = [s.model_dump(by_alias=True, exclude={"id"}) for s in schedules]
        await collection.insert_many(docs)
        return len(docs)

    @classmethod
    async def check_and_run_automated_payroll(cls):
        """
        This is the 'Brain' that runs in the background.
        It checks if today is a cutoff date for an automated schedule.
        """
        collection = db["PayrollSchedules"]
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Find schedules that reach cutoff today, are automated, and not yet processed
        active_schedules = await collection.find({
            "cutoff_date": today,
            "automation_on": True,
            "is_processed": False
        }).to_list(None)

        results = []
        for sched in active_schedules:
            print(f"AUTOMATION: Triggering payroll for {sched['cycle_name']}...")
            
            # 1. Run the actual payroll logic
            count = await PayrollProcessingService.run_full_payroll(
                sched["period_start"], 
                sched["period_end"]
            )
            
            # 2. Mark as processed so we don't run it again
            await collection.update_one(
                {"_id": sched["_id"]},
                {"$set": {
                    "is_processed": True,
                    "processed_at": datetime.now(),
                    "snapshot_count": count
                }}
            )
            results.append({"cycle": sched["cycle_name"], "processed": count})
            
        return results
