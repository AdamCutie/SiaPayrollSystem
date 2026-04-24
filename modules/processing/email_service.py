from __future__ import annotations

import io
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Optional

from bson import ObjectId

from core.config import settings
from core.database import db
from db.models import PayrollSnapshot
from modules.activity_logs.service import ActivityLogService


SENDABLE_STATUSES = {"approved", "completed"}
RETRYABLE_EMAIL_STATUSES = {"failed", "skipped", "pending"}


class PayslipEmailService:
    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _format_date(value: Optional[datetime]) -> str:
        if not value:
            return "N/A"
        return value.strftime("%B %d, %Y")

    @classmethod
    async def _get_snapshot(cls, snapshot_id: str) -> Optional[PayrollSnapshot]:
        doc = await db["PayrollSnapshots"].find_one({"_id": ObjectId(snapshot_id)})
        return PayrollSnapshot(**doc) if doc else None

    @classmethod
    async def _resolve_employee_email(cls, snapshot: PayrollSnapshot) -> Optional[str]:
        doc = await db["SyncedHREmployees"].find_one({
            "$or": [
                {"payload.employeeId": snapshot.employee_number},
                {"payload._id": snapshot.employee_id},
            ]
        })
        if not doc:
            return None
        return doc.get("payload", {}).get("email")

    @classmethod
    def _generate_payslip_pdf(cls, snapshot: PayrollSnapshot) -> bytes:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise RuntimeError(
                "PDF generation dependency is missing. Install requirements to enable payslip email attachments."
            ) from exc

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 48

        pdf.setTitle(f"Payslip_{snapshot.employee_number}")
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(48, y, "SIA Payroll System")
        y -= 22
        pdf.setFont("Helvetica", 11)
        pdf.drawString(
            48,
            y,
            f"Payslip Period: {cls._format_date(snapshot.pay_period_start)} - {cls._format_date(snapshot.pay_period_end)}",
        )
        y -= 16
        pdf.drawString(48, y, f"Pay Date: {cls._format_date(snapshot.pay_date)}")
        y -= 30

        details = [
            ("Employee Code", snapshot.employee_number),
            ("Employee Name", snapshot.full_name),
            ("Department", snapshot.department or "Staff"),
            ("Processed At", cls._format_date(snapshot.processed_at)),
            ("SSS No.", snapshot.sss_number or "---"),
            ("PhilHealth No.", snapshot.philhealth_number or "---"),
            ("Pag-IBIG No.", snapshot.pagibig_number or "---"),
        ]
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(48, y, "Employee Details")
        y -= 18
        pdf.setFont("Helvetica", 10)
        for label, value in details:
            pdf.drawString(54, y, f"{label}: {value}")
            y -= 14

        y -= 10
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(48, y, "Earnings and Deductions")
        y -= 18
        pdf.setFont("Helvetica", 10)
        rows = [
            ("Basic Salary", snapshot.basic_salary),
            ("Overtime", snapshot.total_overtime),
            ("Night Differential", snapshot.total_nd_pay),
            ("Retroactive Adjustment", snapshot.retro_pay),
            ("Holiday Pay", snapshot.holiday_pay),
            ("Special Day Pay", snapshot.special_day_pay),
            ("Allowance Total", snapshot.housing_allowance + snapshot.transport_allowance + snapshot.meal_allowance + snapshot.other_allowances),
            ("Total Deductions", snapshot.total_deductions + snapshot.total_penalties),
            ("Net Pay", snapshot.net_pay),
        ]
        for label, amount in rows:
            pdf.drawString(54, y, label)
            pdf.drawRightString(width - 54, y, f"PHP {float(amount or 0):,.2f}")
            y -= 14

        y -= 10
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(48, y, "Attendance Summary")
        y -= 18
        pdf.setFont("Helvetica", 10)
        pdf.drawString(54, y, f"Days Worked: {snapshot.days_worked}")
        y -= 14
        pdf.drawString(54, y, f"Days Present: {snapshot.days_present}")
        y -= 14
        pdf.drawString(54, y, f"Days Absent: {snapshot.days_absent}")
        y -= 24

        pdf.setFont("Helvetica-Oblique", 9)
        pdf.drawString(48, y, "This is a system-generated payslip. No signature is required.")
        pdf.showPage()
        pdf.save()
        return buffer.getvalue()

    @classmethod
    def _build_email_message(cls, snapshot: PayrollSnapshot, recipient: str, pdf_bytes: bytes) -> EmailMessage:
        subject = f"Your Payslip for {cls._format_date(snapshot.pay_period_start)} - {cls._format_date(snapshot.pay_period_end)}"
        pay_date = cls._format_date(snapshot.pay_date)
        body = (
            f"Hello {snapshot.full_name},\n\n"
            f"Greetings from SIA Payroll System.\n"
            f"Your payslip for {cls._format_date(snapshot.pay_period_start)} to {cls._format_date(snapshot.pay_period_end)} "
            f"is now available. The scheduled pay date is {pay_date}.\n\n"
            "Your payslip PDF is attached to this email.\n\n"
            "Regards,\n"
            "SIA Payroll System"
        )

        msg = EmailMessage()
        msg["Subject"] = subject
        from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{from_email}>" if settings.SMTP_FROM_NAME and from_email else from_email
        msg["To"] = recipient
        msg.set_content(body)
        filename = f"Payslip_{snapshot.employee_number}_{snapshot.pay_period_start.strftime('%Y%m%d')}_{snapshot.pay_period_end.strftime('%Y%m%d')}.pdf"
        msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)
        return msg

    @classmethod
    def _send_smtp_message(cls, message: EmailMessage) -> None:
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            raise RuntimeError("SMTP configuration is incomplete.")

        if settings.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)

        try:
            server.ehlo()
            if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
                server.starttls()
                server.ehlo()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
        finally:
            try:
                server.quit()
            except Exception:
                pass

    @classmethod
    async def _mark_snapshot(
        cls,
        snapshot_id: ObjectId,
        *,
        status: str,
        reason: Optional[str] = None,
        sent_at: Optional[datetime] = None,
    ) -> None:
        await db["PayrollSnapshots"].update_one(
            {"_id": snapshot_id},
            {
                "$set": {
                    "email_delivery_status": status,
                    "email_last_attempt_at": cls._utc_now(),
                    "email_sent_at": sent_at,
                    "email_failure_reason": reason,
                }
            },
        )

    @classmethod
    def _is_sendable_status(cls, status: str) -> bool:
        return str(status or "").casefold() in SENDABLE_STATUSES

    @classmethod
    async def send_snapshot_email(
        cls,
        snapshot_id: str,
        *,
        ignore_due_date: bool = False,
        force_retry: bool = False,
    ) -> dict[str, Any]:
        snapshot = await cls._get_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError("Payroll snapshot not found.")

        if not settings.PAYSLIP_EMAIL_ENABLED:
            raise RuntimeError("Payslip email delivery is disabled.")

        if not cls._is_sendable_status(snapshot.status):
            await cls._mark_snapshot(ObjectId(snapshot_id), status="skipped", reason="Snapshot is not finance-approved.")
            return {"status": "skipped", "reason": "Snapshot is not finance-approved."}

        if not snapshot.pay_date:
            await cls._mark_snapshot(ObjectId(snapshot_id), status="skipped", reason="Snapshot has no pay date.")
            return {"status": "skipped", "reason": "Snapshot has no pay date."}

        now = cls._utc_now()
        pay_date = snapshot.pay_date if snapshot.pay_date.tzinfo else snapshot.pay_date.replace(tzinfo=timezone.utc)
        if not ignore_due_date and pay_date > now:
            return {"status": "pending", "reason": "Pay date has not arrived yet."}

        if snapshot.email_delivery_status == "sent" and not force_retry:
            return {"status": "sent", "reason": "Payslip email already sent."}

        recipient = await cls._resolve_employee_email(snapshot)
        if not recipient:
            reason = "Employee email is missing in synced HR records."
            await cls._mark_snapshot(ObjectId(snapshot_id), status="skipped", reason=reason)
            return {"status": "skipped", "reason": reason}

        try:
            pdf_bytes = cls._generate_payslip_pdf(snapshot)
            message = cls._build_email_message(snapshot, recipient, pdf_bytes)
            cls._send_smtp_message(message)
            sent_at = cls._utc_now()
            await cls._mark_snapshot(ObjectId(snapshot_id), status="sent", reason=None, sent_at=sent_at)
            await ActivityLogService.log_local_activity(
                module="Payroll",
                action="Sent payslip email",
                target_info=f"{snapshot.employee_number} | {snapshot.full_name}",
                metadata={"snapshot_id": snapshot_id, "recipient": recipient, "pay_date": snapshot.pay_date.isoformat()},
            )
            return {"status": "sent", "recipient": recipient, "sent_at": sent_at.isoformat()}
        except Exception as exc:
            reason = str(exc)
            await cls._mark_snapshot(ObjectId(snapshot_id), status="failed", reason=reason)
            await ActivityLogService.log_local_activity(
                module="Payroll",
                action="Payslip email failed",
                target_info=f"{snapshot.employee_number} | {snapshot.full_name}",
                metadata={"snapshot_id": snapshot_id, "reason": reason},
            )
            return {"status": "failed", "reason": reason}

    @classmethod
    async def process_due_payslip_emails(cls) -> dict[str, Any]:
        if not settings.PAYSLIP_EMAIL_ENABLED:
            return {"processed": 0, "results": [], "status": "disabled"}

        now = datetime.now()
        query = {
            "pay_date": {"$lte": now},
            "status": {"$regex": "^(Approved|Completed)$", "$options": "i"},
            "email_delivery_status": {"$ne": "sent"},
        }
        docs = await db["PayrollSnapshots"].find(query).sort("pay_date", 1).to_list(None)
        results = []
        for doc in docs:
            result = await cls.send_snapshot_email(str(doc["_id"]))
            results.append({"snapshot_id": str(doc["_id"]), **result})
        return {"processed": len(results), "results": results, "status": "completed"}

    @classmethod
    async def resend_failed_or_skipped(cls) -> dict[str, Any]:
        if not settings.PAYSLIP_EMAIL_ENABLED:
            return {"processed": 0, "results": [], "status": "disabled"}

        now = datetime.now()
        docs = await db["PayrollSnapshots"].find({
            "pay_date": {"$lte": now},
            "status": {"$regex": "^(Approved|Completed)$", "$options": "i"},
            "email_delivery_status": {"$in": list(RETRYABLE_EMAIL_STATUSES - {"pending"})},
        }).to_list(None)

        results = []
        for doc in docs:
            result = await cls.send_snapshot_email(str(doc["_id"]), ignore_due_date=True, force_retry=True)
            results.append({"snapshot_id": str(doc["_id"]), **result})
        return {"processed": len(results), "results": results, "status": "completed"}
