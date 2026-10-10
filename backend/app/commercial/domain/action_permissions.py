"""Sensitive commercial decisions are independent of ordinary record editing."""
EXTRA_ACTIONS = {
    'quotes': ('issue','accept','reject','expire','revise'),
    'orders': ('confirm','cancel','revise'),
    'samples': ('start','deliver','cancel','reopen','decide'),
    'follow_ups': ('cancel','reopen'),
}
QUOTE_ACTIONS = {a:f'commercial:quotes:{a}' for a in EXTRA_ACTIONS['quotes']}
ORDER_ACTIONS = {a:f'commercial:orders:{a}' for a in EXTRA_ACTIONS['orders']}
SAMPLE_STATUS_PERMISSIONS = {
    'requested':'commercial:samples:reopen', 'in_preparation':'commercial:samples:start',
    'delivered':'commercial:samples:deliver', 'cancelled':'commercial:samples:cancel',
    'evaluated':'commercial:evaluations:create',
}
