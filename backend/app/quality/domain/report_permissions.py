"""Quality report permissions (QUAL-REPORT-001): one per report, independent of registration and presentation. Pure."""
LABELS = {
    'check_full': ('Quality check report', 'تقرير فحص الجودة'),
    'checks_summary': ('Quality checks summary', 'ملخص فحوصات الجودة'),
    'rejections_analysis': ('Rejections and dispositions analysis', 'تحليل الرفض والقرارات'),
    'defects_analysis': ('Defects analysis', 'تحليل العيوب'),
}
REPORT_CHECK_FULL, REPORT_CHECKS_SUMMARY, REPORT_REJECTIONS_ANALYSIS, REPORT_DEFECTS_ANALYSIS = ('reports:quality:' + key for key in LABELS)
ALL: tuple[str, ...] = tuple('reports:quality:' + key for key in LABELS)
