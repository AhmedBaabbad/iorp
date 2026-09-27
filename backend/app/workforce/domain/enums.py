from enum import Enum


class WorkforceMemberStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class EmploymentType(str, Enum):
    EMPLOYEE = "employee"
    CONTRACTOR = "contractor"
    TEMPORARY = "temporary"


class WorkerType(str, Enum):
    FACTORY_MANAGER = "factory_manager"
    PRODUCTION_MANAGER = "production_manager"
    SUPERVISOR = "supervisor"
    OPERATOR = "operator"
    TECHNICIAN = "technician"
    MAINTENANCE_TECHNICIAN = "maintenance_technician"
    HELPER = "helper"
    QUALITY_INSPECTOR = "quality_inspector"
    WAREHOUSE_STAFF = "warehouse_staff"
    LOGISTICS_COORDINATOR = "logistics_coordinator"
    SALES_MANAGER = "sales_manager"
    SALES_REP = "sales_rep"
    PROCUREMENT_OFFICER = "procurement_officer"
    HR_OFFICER = "hr_officer"
    ACCOUNTANT = "accountant"
    SAFETY_OFFICER = "safety_officer"
    ADMIN_SUPPORT = "admin_support"
