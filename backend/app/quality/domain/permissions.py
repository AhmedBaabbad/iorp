"""Quality permissions (QUAL-001): the single source of every quality permission code.

The platform catalog registers these, system roles are generated from them, and routes, services
and the frontend refer to these names only. Pure: no imports from other modules.
"""

MODULE = "quality"

# resource -> actions, in the order the roles screen shows them.
RESOURCES: dict[str, tuple[str, ...]] = {
    "quality_checks": ("read", "create", "update", "start", "close", "cancel", "measure"),
    "rejections": ("read", "create", "update", "decide", "execute"),
    "quality_defects": ("read", "create", "update"),
    # QUAL-NCR-002: "update" works the report through its stages (containment, root cause, actions); "verify" judges the
    # actions' effectiveness and closes it; "cancel" withdraws it.
    "ncr_reports": ("read", "create", "update", "verify", "cancel"),
    # Corrective actions, wherever their owners work: "complete" records an action as done, with its evidence.
    "ncr_actions": ("read", "complete"),
    # QUAL-SPEC-001: test parameters and product specifications (TDS); "activate" puts a revision into force.
    "specifications": ("read", "create", "update", "activate"),
    # QUAL-COA-001: certificates of analysis; "issue" approves and numbers one, "revoke" withdraws an issued one.
    "certificates": ("read", "create", "update", "issue", "revoke"),
}


def code(resource: str, action: str) -> str:
    assert action in RESOURCES[resource], f"{resource}:{action} is not a quality permission"
    return f"{MODULE}:{resource}:{action}"


ALL: tuple[str, ...] = tuple(code(resource, action) for resource, actions in RESOURCES.items() for action in actions)

CHECKS_READ, CHECKS_CREATE, CHECKS_UPDATE, CHECKS_START, CHECKS_CLOSE, CHECKS_CANCEL, CHECKS_MEASURE = (code("quality_checks", a) for a in RESOURCES["quality_checks"])
REJECTIONS_READ, REJECTIONS_CREATE, REJECTIONS_UPDATE, REJECTIONS_DECIDE, REJECTIONS_EXECUTE = (code("rejections", a) for a in RESOURCES["rejections"])
DEFECTS_READ, DEFECTS_CREATE, DEFECTS_UPDATE = (code("quality_defects", a) for a in RESOURCES["quality_defects"])
NCR_READ, NCR_CREATE, NCR_UPDATE, NCR_VERIFY, NCR_CANCEL = (code("ncr_reports", a) for a in RESOURCES["ncr_reports"])
NCR_ACTIONS_READ, NCR_ACTIONS_COMPLETE = (code("ncr_actions", a) for a in RESOURCES["ncr_actions"])
SPECS_READ, SPECS_CREATE, SPECS_UPDATE, SPECS_ACTIVATE = (code("specifications", a) for a in RESOURCES["specifications"])
COA_READ, COA_CREATE, COA_UPDATE, COA_ISSUE, COA_REVOKE = (code("certificates", a) for a in RESOURCES["certificates"])

# action -> permission (allowed actions shown on each record).
CHECK_ACTIONS: dict[str, str] = {"edit": CHECKS_UPDATE, "start": CHECKS_START, "close": CHECKS_CLOSE, "cancel": CHECKS_CANCEL, "measure": CHECKS_MEASURE}
REJECTION_ACTIONS: dict[str, str] = {"edit": REJECTIONS_UPDATE, "decide": REJECTIONS_DECIDE, "execute": REJECTIONS_EXECUTE}
NCR_ACTIONS: dict[str, str] = {"edit": NCR_UPDATE, "contain": NCR_UPDATE, "investigate": NCR_UPDATE, "add_action": NCR_UPDATE,
                               "submit": NCR_UPDATE, "verify": NCR_VERIFY, "cancel": NCR_CANCEL, "review_effectiveness": NCR_VERIFY}

# Labels where "<action> <resource>" reads badly; everything else is composed by the catalog.
LABELS: dict[str, tuple[str, str]] = {
    CHECKS_START: ("Start Quality Inspections", "بدء فحوصات الجودة"),
    CHECKS_CLOSE: ("Close Quality Checks with a Result", "إغلاق فحوصات الجودة بنتيجة"),
    CHECKS_CANCEL: ("Cancel Quality Checks", "إلغاء فحوصات الجودة"),
    REJECTIONS_DECIDE: ("Decide Rejection Dispositions", "اتخاذ قرار حالات الرفض"),
    REJECTIONS_EXECUTE: ("Execute Rejection Decisions", "تنفيذ قرارات حالات الرفض"),
    CHECKS_MEASURE: ("Record Inspection Measurements", "تسجيل قياسات الفحص"),
    SPECS_ACTIVATE: ("Put Product Specifications into Force", "اعتماد مواصفات المنتجات وتفعيلها"),
    COA_ISSUE: ("Approve and Issue Certificates of Analysis", "اعتماد وإصدار شهادات التحليل"),
    COA_REVOKE: ("Revoke Certificates of Analysis", "إلغاء شهادات التحليل"),
    NCR_UPDATE: ("Work Non-Conformance Reports (containment, root cause, actions)", "معالجة تقارير عدم المطابقة (الاحتواء والسبب الجذري والإجراءات)"),
    NCR_VERIFY: ("Verify Corrective Actions and Close NCRs", "التحقق من فعالية الإجراءات وإغلاق تقارير عدم المطابقة"),
    NCR_CANCEL: ("Cancel Non-Conformance Reports", "إلغاء تقارير عدم المطابقة"),
    NCR_ACTIONS_COMPLETE: ("Complete Corrective Actions", "إكمال الإجراءات التصحيحية"),
}
