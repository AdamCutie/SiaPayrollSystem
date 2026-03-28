from fastapi import APIRouter, Depends, HTTPException

from core.auth import CurrentUser, get_current_user, require_admin, require_user
from core.database import db
from integrations.hr.adapter import (
    get_all_active_employees,
    get_employee_by_id,
    get_employee_payroll_config,
    update_payroll_config_override,
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
        
        employee = await get_employee_by_id(employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        full_name = f"{employee.lastName}, {employee.firstName}"
        config = await get_employee_payroll_config(employee.id, employee.employeeId, full_name)
        
        if config:
            # If the database has 0.0, we show the calculated legal values in the UI
            if config.sssContribution == 0:
                config.sssContribution = AgencyCalculator.calculate_sss(config.basicSalary)
            if config.philHealthContribution == 0:
                config.philHealthContribution = AgencyCalculator.calculate_philhealth(config.basicSalary)
            if config.pagIbigContribution == 0:
                config.pagIbigContribution = AgencyCalculator.calculate_pagibig(config.basicSalary)
            
            # Estimate withholding tax for the UI (Gross - Statutory)
            if config.withholdingTax == 0:
                statutory = config.sssContribution + config.philHealthContribution + config.pagIbigContribution
                taxable = max(0, config.basicSalary - statutory)
                config.withholdingTax = AgencyCalculator.calculate_withholding_tax(taxable)
                
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch config: {str(e)}")

@router.post("/{employee_id}/payroll-config")
async def update_payroll_configuration(
    employee_id: str, 
    update_data: HRPayrollConfigUpdate,
    _: object = Depends(require_admin)
):
    """
    Saves a payroll configuration override to OUR database.
    Only used for 'Regular' employees as per HR policy.
    """
    try:
        from integrations.hr.adapter import update_payroll_config_override
        success = await update_payroll_config_override(employee_id, update_data)
        if success:
            return {"status": "success", "message": "Payroll manipulation saved to local DB."}
        else:
            return {"status": "no_change", "message": "No changes were saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save manipulation: {str(e)}")

@router.get("/profile/{employee_id}")
async def get_employee_profile(employee_id: str, user: CurrentUser = Depends(get_current_user)):
    """
    Full Profile View: Combines HR Identity with Payroll History Snapshots.
    """
    try:
        # 1) Identity from HR (supports either MongoDB _id or employee number)
        hr_employee = await get_employee_by_id(employee_id)
        if not hr_employee:
            raise HTTPException(status_code=404, detail="Employee profile not found.")

        # RBAC: employees can only view their own profile
        if user.role != "admin" and hr_employee.id != user.employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own profile.")

        full_name = f"{hr_employee.lastName}, {hr_employee.firstName}"

        # 2) Latest payroll configuration from HR (salary settings)
        payroll_config: HRPayrollConfigRead | None = await get_employee_payroll_config(
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
