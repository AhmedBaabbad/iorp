"""Customer complaint lifecycle (ISO 10002). Commercial owns the customer side and closure; Quality owns the technical
investigation (its non-conformance report and corrective actions).

new ─assign→ processing ─request_close→ pending_closure ─approve_close→ closed ─reopen→ processing
                                          pending_closure ─return→ processing;   new / processing ─cancel→ cancelled

Assigning an owner is the initial assessment (who, which department, by when) and starts the processing itself.
"""
PREFIX = 'commercial:complaints:'
STATUSES = ('new', 'processing', 'pending_closure', 'closed', 'cancelled')
# action -> (from statuses, to status, permission)
ACTIONS = {
    'request_close': (('processing',), 'pending_closure', 'resolve'),
    'approve_close': (('pending_closure',), 'closed', 'close'),
    'return': (('pending_closure',), 'processing', 'close'),
    'reopen': (('closed',), 'processing', 'reopen'),
    'cancel': (('new', 'processing'), 'cancelled', 'cancel'),
}
PERMISSIONS = ('read', 'create', 'update', 'assign', 'investigate', 'resolve', 'close', 'reopen', 'cancel', 'report')
CATEGORIES = ('quality', 'delivery', 'quantity', 'packaging', 'commercial', 'service', 'other')
DEPARTMENTS = ('commercial', 'quality', 'shipping', 'production')


def allowed(status, can):
    return [action for action, (sources, _, permission) in ACTIONS.items() if status in sources and can(PREFIX + permission)]
