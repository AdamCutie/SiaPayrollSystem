from fastapi import APIRouter, Depends, HTTPException

from core.auth import CurrentUser, get_current_user, require_admin, require_user
from core.database import db
from modules.activity_logs.service import ActivityLogService
from integrations.hr.adapter import (
    get_all_active_employees,
    get_synced_employee_by_id,
    get_synced_employee_payroll_config,
)
from integrations.hr.schemas import HREmployeeRead, HRPayrollConfigRead, HRPayrollConfigUpdate
from db.models import PayrollSnapshot
from typing import List, Optional

router = APIRouter(
    prefix="/employees",
    tags=["Employee Management"],
    dependencies=[Depends(require_user)],
)

@router.get("/list", response_model=List[HREmployeeRead], response_model_by_alias=False)
async def get_employee_list(_: object = Depends(require_admin)):
    """
    Fetches the list of all active employees for the management table.
    """
    try:
        return await get_all_active_employees(limit=100)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch employees: {str(e)}")

@router.get("/{employee_id}/payroll-config", response_model=Optional[HRPayrollConfigRead], response_model_by_alias=False)
async def get_payroll_configuration(employee_id: str, _: object = Depends(require_admin)):
    """
    Fetches the payroll configuration for a specific employee.
    If statutory fields are 0, we pre-calculate them for the UI view.
    """
    try:
        from modules.agencies.service import AgencyCalculator
        
        employee = await get_synced_employee_by_id(employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        full_name = f"{employee.lastName}, {employee.firstName}"
        config = await get_synced_employee_payroll_config(employee.id, employee.employeeId, full_name)
        
        if config:
            # Always recalculate statutory preview values in the UI from current law-based rules.
            sss_breakdown = AgencyCalculator.calculate_sss_breakdown(config.basicSalary)
            config.sssContribution = sss_breakdown["employee_total"]
            config.sssEmployeeShare = sss_breakdown["employee_share"]
            config.sssEmployerShare = sss_breakdown["employer_share"]
            config.sssECEmployer = sss_breakdown["ec_employer"]
            config.sssMPFEmployeeShare = sss_breakdown["mpf_employee_share"]
            config.sssMPFEmployerShare = sss_breakdown["mpf_employer_share"]
            config.sssMonthlySalaryCredit = sss_breakdown["monthly_salary_credit"]
            config.philHealthContribution = AgencyCalculator.calculate_philhealth(config.basicSalary)
            config.pagIbigContribution = AgencyCalculator.calculate_pagibig(config.basicSalary)
            
            # Use the standardized semi-monthly tax estimator from our Adapter
            from integrations.hr.adapter import _calculate_estimated_withholding_tax
            config.withholdingTax = _calculate_estimated_withholding_tax(config.basicSalary)
                
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch config: {str(e)}")

@router.get("/profile/{employee_id}")
async def get_employee_profile(employee_id: str, user: CurrentUser = Depends(get_current_user)):
    """
    Full Profile View: Combines HR Identity with Payroll History Snapshots.
    """
    try:
        # 1) Identity from HR (supports either MongoDB _id or employee number)
        hr_employee = await get_synced_employee_by_id(employee_id)
        if not hr_employee:
            raise HTTPException(status_code=404, detail="Employee profile not found.")

        # RBAC: employees can only view their own profile
        if user.role != "admin" and hr_employee.id != user.employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own profile.")

        full_name = f"{hr_employee.lastName}, {hr_employee.firstName}"

        # 2) Latest payroll configuration from HR (salary settings)
        payroll_config: HRPayrollConfigRead | None = await get_synced_employee_payroll_config(
            hr_employee.id,
            hr_employee.employeeId,
            full_name,
        )

        # 3) History from our New Database (snapshots)
        history_coll = db["PayrollSnapshots"]
        cursor = history_coll.find({"employee_id": hr_employee.id}).sort("processed_at", -1).limit(10)
        history = [PayrollSnapshot(**doc) async for doc in cursor]

        return {
            "identity": hr_employee,
            "payroll_config": payroll_config,
            "payroll_history": history,
            "status": "Active" if hr_employee.isActive else "Inactive"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving profile: {str(e)}")
