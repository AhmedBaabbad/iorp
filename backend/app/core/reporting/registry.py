from app.core.reporting.contracts import ReportDefinition


class ReportRegistry:
    def __init__(self):
        self.definitions: dict[str, ReportDefinition] = {}

    def register(self, definition):
        if definition.key in self.definitions:
            raise ValueError('Duplicate report key')
        self.definitions[definition.key] = definition

    def get(self, key):
        return self.definitions.get(key)


registry = ReportRegistry()
