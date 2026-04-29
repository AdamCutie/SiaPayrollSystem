from __future__ import annotations

import asyncio
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
    def _format_date(value: Any, format: str = "%B %d, %Y") -> str:
        if not value:
            return "N/A"
        if isinstance(value, str):
            try:
                # Handle potential ISO format strings from MongoDB/Pydantic
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        return value.strftime(format)

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
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.platypus import Table, TableStyle
        except ImportError as exc:
            raise RuntimeError(
                "PDF generation dependency is missing. Install requirements to enable payslip email attachments."
            ) from exc

        buffer = io.BytesIO()
        width, height = A4
        pdf = canvas.Canvas(buffer, pagesize=A4)
        pdf.setTitle(f"Payslip_{snapshot.employee_number}")

        def fcy(val):
            return f"{float(val or 0):,.2f}"

        # --- Base Styles ---
        y_cursor = height - 40
        margin = 40
        content_width = width - (2 * margin)

        # 1. Header
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(width / 2, y_cursor, "ELECTRONIC SALARY STATEMENT")
        y_cursor -= 18
        pdf.setFont("Helvetica", 9)
        pdf.drawCentredString(width / 2, y_cursor, f"Period: {cls._format_date(snapshot.pay_period_start)} - {cls._format_date(snapshot.pay_period_end)}")
        
        if snapshot.pay_date:
            y_cursor -= 12
            pdf.setFont("Helvetica-Bold", 9)
            pdf.setFillColor(colors.HexColor("#0d6efd"))
            pdf.drawCentredString(width / 2, y_cursor, f"Scheduled Payday: {cls._format_date(snapshot.pay_date)}")
            pdf.setFillColor(colors.black)

        y_cursor -= 20

        # 2. Employee Info Table (Structured to prevent overflow)
        info_data = [
            ["Employee Code:", str(snapshot.employee_number), "SSS No:", str(snapshot.sss_number or "---")],
            ["Employee Name:", str(snapshot.full_name).upper()[:40], "PhilHealth No:", str(snapshot.philhealth_number or "---")],
            ["Designation:", (snapshot.department or "Staff")[:30], "Pag-IBIG No:", str(snapshot.pagibig_number or "---")],
            ["Hourly Salary:", fcy(snapshot.hourly_rate), "", ""]
        ]
        info_table = Table(info_data, colWidths=[90, 160, 90, 130])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), # Labels bold
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'), # Labels bold
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        w, h = info_table.wrap(content_width, height)
        info_table.drawOn(pdf, margin, y_cursor - h)
        y_cursor -= (h + 20)

        # 3. Main Tables (Earnings & Deductions)
        col_w = content_width / 2
        
        earn_data = [["Description", "Hrs", "Total"]]
        earn_data.append(["BASIC PAY", "---", fcy(snapshot.basic_salary)])
        if snapshot.total_overtime > 0:
            earn_data.append(["OVERTIME PAY", f"{snapshot.total_overtime_hours:.2f}", fcy(snapshot.total_overtime)])
        if snapshot.total_nd_pay > 0:
            earn_data.append(["NIGHT DIFFERENTIAL", f"{snapshot.total_nd_hours:.2f}", fcy(snapshot.total_nd_pay)])
        if snapshot.retro_pay != 0:
            earn_data.append(["RETROACTIVE ADJ.", "---", fcy(snapshot.retro_pay)])
        if snapshot.holiday_pay > 0:
            earn_data.append(["HOLIDAY PAY", "---", fcy(snapshot.holiday_pay)])
        
        taxable_sum = (snapshot.basic_salary or 0) + (snapshot.total_overtime or 0) + \
                      (snapshot.total_nd_pay or 0) + (snapshot.holiday_pay or 0) + (snapshot.retro_pay or 0)
        
        earn_data.append(["TOTAL TAXABLE (A)", "", fcy(taxable_sum)])
        earn_data.append(["ALLOWANCES (B)", "", fcy(snapshot.housing_allowance + snapshot.transport_allowance + snapshot.meal_allowance + snapshot.other_allowances)])

        ded_data = [["Description", "Total"]]
        ded_data.append(["SSS EE SHARE", fcy(snapshot.sss_deduction)])
        ded_data.append(["PHIC EE SHARE", fcy(snapshot.philhealth_deduction)])
        ded_data.append(["HDMF EE SHARE", fcy(snapshot.pagibig_deduction)])
        
        mand_sum = (snapshot.sss_deduction or 0) + (snapshot.philhealth_deduction or 0) + (snapshot.pagibig_deduction or 0)
        ded_data.append(["TOTAL MANDATORY (D)", fcy(mand_sum)])
        
        other_ded_sum = (snapshot.absence_deduction or 0) + (snapshot.total_loans or 0) + (snapshot.total_penalties or 0)
        ded_data.append(["LOANS & PENALTIES (E)", fcy(other_ded_sum)])
        ded_data.append(["WITHHOLDING TAX (F)", fcy(snapshot.withholding_tax)])

        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.black),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ])

        t_earn = Table(earn_data, colWidths=[col_w * 0.55, col_w * 0.15, col_w * 0.3])
        t_earn.setStyle(table_style)
        t_ded = Table(ded_data, colWidths=[col_w * 0.7, col_w * 0.3])
        t_ded.setStyle(table_style)

        w1, h1 = t_earn.wrap(col_w, height)
        w2, h2 = t_ded.wrap(col_w, height)
        main_h = max(h1, h2)
        
        t_earn.drawOn(pdf, margin, y_cursor - main_h)
        t_ded.drawOn(pdf, margin + col_w, y_cursor - main_h)
        y_cursor -= (main_h + 15)

        # 4. Gross and Net Pay Sections
        # Gross Box
        pdf.setFillColor(colors.HexColor("#f8f9fa"))
        pdf.rect(margin, y_cursor - 20, content_width, 20, fill=1)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(margin + 10, y_cursor - 13, f"GROSS EARNINGS (A+B):  PHP {fcy(snapshot.gross_pay)}")
        total_all_ded = mand_sum + other_ded_sum + (snapshot.withholding_tax or 0)
        pdf.drawRightString(width - margin - 10, y_cursor - 13, f"TOTAL DEDUCTIONS (D+E+F): PHP {fcy(total_all_ded)}")
        
        y_cursor -= 50

        # Net Pay Banner
        pdf.setFillColor(colors.HexColor("#00F5D4"))
        pdf.rect(margin, y_cursor, content_width, 25, fill=1, stroke=1)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(margin + 10, y_cursor + 8, "NET TAKE HOME PAY")
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawRightString(width - margin - 10, y_cursor + 8, f"PHP {fcy(snapshot.net_pay)}")

        y_cursor -= 30

        # 5. Loan & Adjustments Table
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(margin, y_cursor, "LOAN & ADJUSTMENT DETAILS")
        y_cursor -= 5
        
        adj_data = [["Type / Reason", "Amount / Detail"]]
        adj_data.append(["SSS Loan", fcy(snapshot.sss_loan)])
        adj_data.append(["Pag-IBIG Loan", fcy(snapshot.pagibig_loan)])
        adj_data.append(["Company Loan", fcy(snapshot.company_loan)])
        
        # Add a few items if they exist
        for item in snapshot.retro_items[:2]:
            adj_data.append([f"Retro: {item.get('reason')}", fcy(item.get('amount'))])
        
        t_adj = Table(adj_data, colWidths=[content_width * 0.7, content_width * 0.3])
        t_adj.setStyle(table_style)
        _, ha = t_adj.wrap(content_width, height)
        t_adj.drawOn(pdf, margin, y_cursor - ha)
        y_cursor -= (ha + 25)

        # 6. Attendance & YTD (Side by Side)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(margin, y_cursor, "ATTENDANCE & YTD SUMMARY")
        y_cursor -= 5
        
        att_data = [
            ["Attendance", "Days"],
            ["Worked", str(snapshot.days_worked)],
            ["Present", str(snapshot.days_present)],
            ["Absent", str(snapshot.days_absent)]
        ]
        ytd = snapshot.ytd_data or {}
        ytd_data = [
            ["YTD Component", "Total"],
            ["Taxable Income", fcy(ytd.get("ytd_taxable_income", 0))],
            ["SSS EE Contri", fcy(ytd.get("ytd_sss_contribution", 0))],
            ["Withholding Tax", fcy(ytd.get("ytd_wtax", 0))]
        ]
        
        t_att = Table(att_data, colWidths=[col_w * 0.7, col_w * 0.3])
        t_att.setStyle(table_style)
        t_ytd = Table(ytd_data, colWidths=[col_w * 0.7, col_w * 0.3])
        t_ytd.setStyle(table_style)
        
        _, h_att = t_att.wrap(col_w, height)
        _, h_ytd = t_ytd.wrap(col_w, height)
        side_h = max(h_att, h_ytd)
        
        t_att.drawOn(pdf, margin, y_cursor - side_h)
        t_ytd.drawOn(pdf, margin + col_w, y_cursor - side_h)

        # 7. Footer (Fixed Absolute Positioning)
        pdf.setFont("Helvetica-Oblique", 7)
        pdf.setFillColor(colors.gray)
        pdf.drawCentredString(width / 2, 35, "This is a system-generated electronic payslip for SIA Payroll System. No signature is required.")
        pdf.drawCentredString(width / 2, 25, f"Generated on: {cls._format_date(snapshot.processed_at, '%Y-%m-%d %H:%M:%S')}")

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
        filename = f"Payslip_{snapshot.employee_number}_{cls._format_date(snapshot.pay_period_start, '%Y%m%d')}_{cls._format_date(snapshot.pay_period_end, '%Y%m%d')}.pdf"
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
        update_data = {
            "email_delivery_status": status,
            "email_last_attempt_at": cls._utc_now(),
            "email_sent_at": sent_at,
            "email_failure_reason": reason,
        }
        
        # Automation: If email is successfully sent, mark the main status as Completed
        if status == "sent":
            update_data["status"] = "Completed"
            
        await db["PayrollSnapshots"].update_one(
            {"_id": snapshot_id},
            {"$set": update_data},
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
    async def send_all_approved_emails(cls, ignore_due_date: bool = True) -> dict[str, Any]:
        """
        Sends emails for ALL snapshots that are Approved/Completed but haven't been sent yet.
        """
        if not settings.PAYSLIP_EMAIL_ENABLED:
            return {"processed": 0, "results": [], "status": "disabled"}

        now = cls._utc_now()
        query = {
            "status": {"$regex": "^(Approved|Completed)$", "$options": "i"},
            "email_delivery_status": {"$ne": "sent"},
        }
        
        if not ignore_due_date:
            query["pay_date"] = {"$lte": now}

        docs = await db["PayrollSnapshots"].find(query).to_list(None)

        results = []
        for doc in docs:
            result = await cls.send_snapshot_email(str(doc["_id"]), ignore_due_date=True, force_retry=True)
            results.append({"snapshot_id": str(doc["_id"]), **result})
            # 🕒 ADDED: 1-second delay to prevent SMTP "Connection unexpectedly closed"
            await asyncio.sleep(1) 
        return {"processed": len(results), "results": results, "status": "completed"}

    @classmethod
    async def resend_failed_or_skipped(cls, ignore_due_date: bool = True) -> dict[str, Any]:
        if not settings.PAYSLIP_EMAIL_ENABLED:
            return {"processed": 0, "results": [], "status": "disabled"}

        now = cls._utc_now()
        query = {
            "status": {"$regex": "^(Approved|Completed)$", "$options": "i"},
            "email_delivery_status": {"$in": list(RETRYABLE_EMAIL_STATUSES - {"pending"})},
        }
        
        # Only check pay_date if we aren't ignoring the due date (e.g., manual trigger)
        if not ignore_due_date:
            query["pay_date"] = {"$lte": now}

        docs = await db["PayrollSnapshots"].find(query).to_list(None)

        results = []
        for doc in docs:
            result = await cls.send_snapshot_email(str(doc["_id"]), ignore_due_date=True, force_retry=True)
            results.append({"snapshot_id": str(doc["_id"]), **result})
            # 🕒 ADDED: 1-second delay to prevent SMTP "Connection unexpectedly closed"
            await asyncio.sleep(1)
        return {"processed": len(results), "results": results, "status": "completed"}
