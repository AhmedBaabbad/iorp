"""Composition supplies public read APIs; builders never import another module's ORM."""
commercial_factory = None
production_factory = None
identity_factory = None
# There is no tenant module subscription model. Only composed modules are enabled;
# an installation can replace this hook with its tenant capability provider.
module_enabled = lambda db, tenant, module: module in {'commercial', 'production'}
