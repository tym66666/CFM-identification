"""Public field combinations for local-effect information, not source truth.

The same rules feed the request schema, parser and bounded recheck diagnostics.
No candidate correction, population promotion, approval or mathematical routing.
"""
from dataclasses import dataclass

VERSION = 'effect-information-combinations-1'


@dataclass(frozen=True)
class Combination:
    field: str
    trigger: str
    required_field: str
    required_value: str
    error_code: str

    def violated(self, source):
        value = getattr(source, self.field)
        active = bool(value) if self.trigger == 'nonempty' else value == self.trigger
        return active and getattr(source, self.required_field) != self.required_value

    def schema(self):
        condition = {'minItems': 1} if self.trigger == 'nonempty' else {'const': self.trigger}
        return {'if': {'properties': {self.field: condition}, 'required': [self.field]},
                'then': {'properties': {self.required_field: {'const': self.required_value}},
                         'required': [self.required_field]}}

    def diagnostic(self, index):
        # Locate the pair, without deciding which supplied value misreads source.
        return dict(field_path=f'/information/{index}', error_code=self.error_code,
                    field_combination=dict(field=self.field, trigger=self.trigger,
                        required_field=self.required_field, required_value=self.required_value))


RULES = (
    Combination('operator', 'FINITE_SAMPLE', 'availability', 'FINITE_SAMPLE', 'SAMPLE_OPERATOR_REQUIRES_SAMPLE_AVAILABILITY'),
    Combination('availability', 'FINITE_SAMPLE', 'operator', 'FINITE_SAMPLE', 'SAMPLE_AVAILABILITY_REQUIRES_SAMPLE_OPERATOR'),
    Combination('arm_cells', 'nonempty', 'operator', 'NODE_ARM_MEANS', 'ARM_CELLS_REQUIRE_ARM_INFORMATION'),
)


def require(source):
    for rule in RULES:
        if rule.violated(source):
            raise ValueError(rule.error_code)


def diagnose(information):
    return [rule.diagnostic(i) for i, source in enumerate(information)
            for rule in RULES if rule.violated(source)][:50]


def annotate(schema):
    schema['$defs']['EffectInformation'].setdefault('allOf', []).extend(r.schema() for r in RULES)
