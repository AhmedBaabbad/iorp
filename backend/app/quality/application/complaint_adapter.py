"""Open an existing Quality workflow without claiming the complaint is verified."""
from app.quality.application.ncr_service import NCRService


def refer_complaint(db, tenant, *, number, title, statement, customer_id, customer_name):
    report = NCRService(db, tenant).open_report(
        source_type='other', report_type='other', title=f'{number}: {title}'[:255],
        description=f'شكوى العميل رقم {number}\nبلاغ العميل كما ورد (لم يُتحقق منه بعد):\n{statement}',
        customer_id=customer_id, customer_name=customer_name, reference_code=number)
    return report.id, report.report_number
