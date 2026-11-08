"""Developer reading settings; not user route selection or science approval.

Defaults match business_intake.start. This object initializes a new intake;
it does not rewrite historical checkpoints or migrate existing approvals.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, model_validator, model_serializer
from cfm_id_llm.assignment_semantics import Profile as AssignmentProfile
from cfm_id_llm.target_summary_contract import Profile as TargetSummaryProfile
from cfm_id_llm.compact_reference_contract import Profile as A0ReferenceProfile
from cfm_id_llm.compact_response_contract import Profile as A0ResponseProfile, UNIFIED_PROFILES, LOCAL_COMPARISON_PROFILES
from cfm_id_llm.network_fact_protocols import NetworkFactProfile
from cfm_id_llm.network_observational_signature_reading import Profile as ObservationalProfile

ReadingFormat = Literal['canonical', 'compact']
FactFormat = Literal['source_hash', 'short_refs']


class ReadingConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    version: Literal['business-reading-config-1'] = 'business-reading-config-1'
    reading_format: ReadingFormat = 'compact'
    fact_format: FactFormat = 'short_refs'
    assignment_semantics: AssignmentProfile = None
    target_summary_contract: TargetSummaryProfile = None
    a0_reference_contract: A0ReferenceProfile = None
    a0_response_contract: A0ResponseProfile = None
    network_fact_contract: NetworkFactProfile = None
    observational_fact_profile: ObservationalProfile = None
    material_handoff: Literal['information-inventory-1'] | None = None

    @model_serializer(mode='wrap')
    def historical_options(self, handler):
        result = handler(self)
        if result.get('material_handoff') is None:result.pop('material_handoff',None)
        if result.get('observational_fact_profile') is None:result.pop('observational_fact_profile',None)
        return result

    @model_validator(mode='after')
    def compatible_options(self):
        if self.material_handoff and (self.reading_format!='compact' or self.fact_format!='short_refs'):
            raise ValueError('MATERIAL_HANDOFF_REQUIRES_COMPACT_AND_SHORT_REFS')
        if self.a0_response_contract in (*UNIFIED_PROFILES, *LOCAL_COMPARISON_PROFILES) and self.target_summary_contract not in (None,'target-summary-3'):
            raise ValueError('UNIFIED_CONTRACT_REQUIRES_CURRENT_TARGET_SEMANTICS')
        if self.reading_format != 'compact' and any(v is not None for v in (
                self.assignment_semantics, self.target_summary_contract,
                self.a0_reference_contract, self.a0_response_contract)):
            raise ValueError('COMPACT_READING_REQUIRED_FOR_A0_OPTIONS')
        if self.observational_fact_profile is not None and self.fact_format != 'short_refs':
            raise ValueError('OBSERVATIONAL_PROFILE_REQUIRES_SHORT_REFS')
        if self.network_fact_contract is not None and self.fact_format != 'short_refs':
            raise ValueError('NETWORK_FACT_CONTRACT_REQUIRES_SHORT_REFS')
        return self

    def intake_options(self):
        # Revalidate even model_copy/model_construct instances; do not let those
        # Pydantic escape hatches silently bypass configuration validation.
        checked = ReadingConfig.model_validate(self.model_dump(mode='json'))
        return checked.model_dump(mode='json', exclude={'version'})
