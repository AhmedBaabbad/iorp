"""Customer reporting permission catalog, independent of registration and presentation."""
LABELS = {
    'customer_profile': ('Customer profile', 'ملف العميل'),
    'directory': ('Customers directory', 'دليل العملاء'),
    'activity_summary': ('Customer activity and ranking', 'نشاط العملاء وترتيبهم'),
    'quotations_report': ('Quotations report', 'تقرير عروض الأسعار'),
    'demand_fulfillment': ('Demand and fulfillment status', 'حالة الطلب والتخصيص'),
    'growth_retention': ('Customer growth and inactivity', 'نمو العملاء والخمول'),
    'customer_statement': ('Customer order status statement', 'كشف حالة طلبات العميل'),
    'internal_audience': ('Internal customer reports audience', 'الجمهور الداخلي لتقارير العملاء'),
}
ALL = tuple('reports:customers:' + key for key in LABELS)
SALES = ('reports:customers:customer_profile', 'reports:customers:customer_statement',
         'reports:customers:demand_fulfillment', 'reports:customers:internal_audience')
