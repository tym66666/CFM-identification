"""Reviewed, schema-limited JSON -> ORIGINAL v2.8 typed inquiry constructors.

This adapter does NOT admit A4/A5; all concrete source and assumption records
must be separately supplied and their exact snapshots independently approved.
No arbitrary import paths, callables, pickles or provided certificates.
"""
from __future__ import annotations

from fractions import Fraction
import json
from typing import Literal
from pydantic import Field, model_validator

from cfm_id_llm.schemas import StrictModel
from pfn_pipeline._internal.identification.schemas import Assumption, NetworkExposureSpec
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, fixed_policy_target_from_context, declare_network_a4_source,
)
from pfn_pipeline.identification_business import (
    ArmInquiryV21, EffectsInquiryV21, FixedPolicyInquiryV21, FinitePolicyInquiryV21,
    ObservationalPolicyInquiryV23, ObservationalEffectsInquiryV26,
    ObservationalExposureAdjustedEffectsInquiryV27P2,
    ObservationalNodewiseAdjustedEffectsInquiryV28,
)
from pfn_pipeline.identification import make_heterogeneous_bernoulli_arm_task
from pfn_pipeline.identification_batch import identify_randomized_network_batch
from pfn_pipeline.identification_a4_shadow import declare_a4_source
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_policy_r1b import identify_verified_fixed_policy
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, admit_mean_signature_sufficiency,
    declare_signature_population_source,
)
from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23
from pfn_pipeline.identification_observational_exposure_adjustment import (
    declare_stratified_observational_arm_population_v27p2,
    admit_exposure_adjustment_a5_v27p2,
)
from pfn_pipeline.identification_observational_nodewise_adjustment import (
    declare_nodewise_local_arm_population_v28,admit_nodewise_adjustment_a5_v28,
)
from pfn_pipeline.identification_observational_nodewise_mixture_a4 import (
    declare_nodewise_correlated_arm_population_v28p2,
)
from .bridge import ScientificAdmissionV29, FormalQueryBindingV29
from .d1_binding import ReviewedD1ArmPacketV29, prepare_d1_arm_binding_v29

FAMILIES=("R1A_ARM","R1A_EFFECT","R1B_FIXED_POLICY","R2_FIXED_POLICY",
          "R1B_FINITE_POLICY","R3_POLICY","R3_P_STANDARDIZED",
          "R3_EXPOSURE_ADJUSTED","R3_NODEWISE_ADJUSTED")

class ReviewedTypedInquiryPacketV291(StrictModel):
    """Closed set of supported recipe types; all nested keys are checked by builder."""
    schema_version: Literal['causal-idfm-reviewed-typed-inquiry-v2.9.1']='causal-idfm-reviewed-typed-inquiry-v2.9.1'
    formal_family: Literal["R1A_ARM","R1A_EFFECT","R1B_FIXED_POLICY","R2_FIXED_POLICY",
                           "R1B_FINITE_POLICY","R3_POLICY","R3_P_STANDARDIZED",
                           "R3_EXPOSURE_ADJUSTED","R3_NODEWISE_ADJUSTED"]
    scientific_admission: ScientificAdmissionV29
    recipe: dict = Field(min_length=1)

    @model_validator(mode='after')
    def coherent(self):
        if self.formal_family!=self.scientific_admission.formal_family:
            raise ValueError('Packet formal family and reviewed admission must agree')
        if len(json.dumps(self.recipe,ensure_ascii=False,allow_nan=False))>500000:
            raise ValueError('Oversized reviewed JSON recipe; resource guard')
        return self


def _keys(d, required, optional=()):
    if type(d) is not dict or not set(required)<=set(d) or set(d)-set(required)-set(optional):
        raise ValueError('Unsupported or missing field in reviewed typed packet recipe')


def _tuple2(xs):
    return tuple(tuple(x) for x in xs)


def _study(v):
    _keys(v,('network_id','node_order','undirected_edges','treatment_variable',
             'outcome_variable','outcome_kind','context_reference','observation_regime',
             'assignment_design','protocol_provenance','network_provenance',
             'graph_timing_claim'))
    return declare_network_study(**{**v,'node_order':tuple(v['node_order']),
                                 'undirected_edges':_tuple2(v['undirected_edges'])})


def _a5(v):
    if type(v) is not list or not v:
        raise ValueError('Explicit nonempty A5 list is required')
    return tuple(Assumption.model_validate(x) for x in v)


def _policy(st, v, synthetic):
    _keys(v,('assignment',),('unit_weights',))
    w=tuple(v['unit_weights']) if 'unit_weights' in v else None
    return fixed_policy_target_from_context(st,tuple(v['assignment']),
        authority='TRUSTED_FIXTURE' if synthetic else 'HUMAN_CONFIRMED',unit_weights=w)


def _r1b_source(st,v):
    _keys(v,('source_id','operator','provenance','admission','availability','outcome_nodes'),
          ('assignment_cells','exposure_fingerprint'))
    return declare_network_a4_source(st,**{**v,
          'outcome_nodes':tuple(v['outcome_nodes']),
          'assignment_cells':_tuple2(v.get('assignment_cells',())),})


def _signature(st,v):
    _keys(v,('grouping',),('core_collaborators',))
    core={n:tuple(xs) for n,xs in v.get('core_collaborators',{}).items()}
    return declare_policy_signature(st,grouping=v['grouping'],
        core_collaborators=core if core else None)


def _effect(v):
    _keys(v,('kind','node_weights','reference_exposure','comparison_exposure'),
          ('spillover_own_treatment','cohort_authority','cohort_evidence'))
    return EffectQueryV18(**{**v,'node_weights':_tuple2(v['node_weights'])})


def _observational_source(st,v):
    _keys(v,('source_id','provenance','assignment_masses','outcome_nodes','admission','availability'))
    return declare_observational_population_v23(st,source_id=v['source_id'],
        provenance=v['provenance'],assignment_masses=[(tuple(t),p) for t,p in v['assignment_masses']],
        outcome_nodes=tuple(v['outcome_nodes']),admission=v['admission'],
        availability=v['availability'])


def _sufficiency(st,sig,v):
    _keys(v,('assumption','covered_nodes'))
    return admit_mean_signature_sufficiency(st,sig,
        assumption=Assumption.model_validate(v['assumption']),
        covered_nodes=tuple(v['covered_nodes']))


def _r2_source(st,sig,v):
    _keys(v,('source_id','operator','outcome_nodes','provenance','admission','availability'),
          ('signature_cells',))
    return declare_signature_population_source(st,sig,
        source_id=v['source_id'],operator=v['operator'],
        outcome_nodes=tuple(v['outcome_nodes']),provenance=v['provenance'],
        admission=v['admission'],availability=v['availability'],
        signature_cells=_tuple2(v.get('signature_cells',())))


def _d1_design(v,a):
    _keys(v,('network_id','node_order','undirected_edges','propensities','target_node_id',
             'target_own_treatment','target_exposure','protocol_evidence'),
          ('outcome_kind','exposure_definition'))
    net=NetworkExposureSpec(network_id=v['network_id'],node_ids=v['node_order'],
                            undirected_edges=_tuple2(v['undirected_edges']))
    task=make_heterogeneous_bernoulli_arm_task(net,propensities=v['propensities'],
        node_id=v['target_node_id'],own_treatment_value=v['target_own_treatment'],
        exposure_value=v['target_exposure'],source=a.a4_population_operator_reference,
        evidence=f'Independent scientific review {a.scientific_reviewer}: {a.evidence_reference}; '
                 f'A5 {a.a5_assumption_reference}; protocol {v["protocol_evidence"]}',
        admitted=True,synthetic=a.is_synthetic_fixture,
        query_authority='TRUSTED_FIXTURE' if a.is_synthetic_fixture else 'HUMAN_CONFIRMED',
        outcome_kind=v.get('outcome_kind','continuous'),
        exposure_definition=v.get('exposure_definition','strict_majority'))
    return task


def construct_reviewed_typed_binding_v291(packet:ReviewedTypedInquiryPacketV291)->FormalQueryBindingV29:
    """Closed whitelist of constructors; NO scientific admission inferred here."""
    if not isinstance(packet,ReviewedTypedInquiryPacketV291):
        raise TypeError('Validated reviewed packet required')
    a=packet.scientific_admission
    r=packet.recipe
    f=packet.formal_family
    if f=='R1A_ARM':
        _keys(r,('d1',))
        # Use the exact preexisting D1 adapter (it verifies packet coordinates).
        old=ReviewedD1ArmPacketV29.model_validate({'scientific_admission':a,**r['d1']})
        return prepare_d1_arm_binding_v29(old)
    if f=='R1A_EFFECT':
        _keys(r,('d1','effect','a4_source'))
        task=_d1_design(r['d1'],a)
        batch=identify_randomized_network_batch(task)
        v=r['a4_source']
        _keys(v,('source_id','operator','provenance','admission','availability','outcome_nodes'),
              ('arm_cells','assignment_cells'))
        source=declare_a4_source(task,source_id=v['source_id'],operator=v['operator'],
          provenance=v['provenance'],admission=v['admission'],availability=v['availability'],
          outcome_nodes=tuple(v['outcome_nodes']),node_order=batch.node_ids,
          arm_cells=_tuple2(v.get('arm_cells',())),
          assignment_cells=_tuple2(v.get('assignment_cells',())))
        inquiry=EffectsInquiryV21(batch,source,(_effect(r['effect']),))
    else:
        _keys(r,('study','assumptions'),('policy','a4_source','a4_sources','signature',
            'sufficiency','effect','license','components','probabilities'))
        st=_study(r['study']); assumptions=_a5(r['assumptions'])
        if f in ('R1B_FIXED_POLICY','R2_FIXED_POLICY','R1B_FINITE_POLICY','R3_POLICY'):
            if f=='R1B_FINITE_POLICY':
                if not isinstance(r.get('components'),list) or not r['components'] or 'probabilities' not in r:
                    raise ValueError('Positive finite policy components required')
                source=_r1b_source(st,r['a4_source'])
                components=[]
                for v in r['components']:
                    _keys(v,('policy',))
                    t=_policy(st,v['policy'],a.is_synthetic_fixture)
                    components.append(identify_verified_fixed_policy(st,t,(source,),assumptions=assumptions))
                inquiry=FinitePolicyInquiryV21(tuple(components),tuple(r['probabilities']))
            else:
                target=_policy(st,r['policy'],a.is_synthetic_fixture)
                if f=='R1B_FIXED_POLICY':
                    inquiry=FixedPolicyInquiryV21(st,target,assumptions,
                        r1b_sources=(_r1b_source(st,r['a4_source']),))
                elif f=='R2_FIXED_POLICY':
                    sig=_signature(st,r['signature'])
                    inquiry=FixedPolicyInquiryV21(st,target,assumptions,
                        r2_signature=sig,r2_sufficiency=_sufficiency(st,sig,r['sufficiency']),
                        r2_sources=tuple(_r2_source(st,sig,x) for x in r['a4_sources']))
                else:
                    source=_observational_source(st,r['a4_source'])
                    sig=_signature(st,r['signature']) if r.get('signature') else None
                    suff=_sufficiency(st,sig,r['sufficiency']) if r.get('sufficiency') else None
                    inquiry=ObservationalPolicyInquiryV23(st,target,source,assumptions,sig,suff)
        else:
            sig=_signature(st,r['signature'])
            effect=(_effect(r['effect']),)
            if f=='R3_P_STANDARDIZED':
                source=_observational_source(st,r['a4_source'])
                inquiry=ObservationalEffectsInquiryV26(st,source,assumptions,sig,effect)
            elif f=='R3_EXPOSURE_ADJUSTED':
                v=r['a4_source']
                _keys(v,('source_id','provenance','adjustment_variable','strata','covered_cells',
                         'admission','availability'))
                source=declare_stratified_observational_arm_population_v27p2(st,sig,
                    source_id=v['source_id'],provenance=v['provenance'],
                    adjustment_variable=v['adjustment_variable'],
                    strata=[(x[0],x[1],x[2]) for x in v['strata']],
                    covered_cells=_tuple2(v['covered_cells']),
                    admission=v['admission'],
                    availability=v['availability'])
                lic=r['license'];_keys(lic,('covered_nodes','potential_outcome_exposure_sufficiency',
                                           'exposure_level_conditional_exchangeability'))
                license=admit_exposure_adjustment_a5_v27p2(st,sig,
                    covered_nodes=tuple(lic['covered_nodes']),
                    potential_outcome_exposure_sufficiency=Assumption.model_validate(lic['potential_outcome_exposure_sufficiency']),
                    exposure_level_conditional_exchangeability=Assumption.model_validate(lic['exposure_level_conditional_exchangeability']))
                inquiry=ObservationalExposureAdjustedEffectsInquiryV27P2(st,source,assumptions,sig,license,effect)
            elif f=='R3_NODEWISE_ADJUSTED':
                v=r['a4_source']
                _keys(v,('source_id','provenance','feature_name','profiles','covered_cells',
                          'admission','availability'),('factorization_kind',))
                kwargs=dict(source_id=v['source_id'],provenance=v['provenance'],
                    feature_name=v['feature_name'],profiles=v['profiles'],
                    covered_cells=_tuple2(v['covered_cells']),
                    admission=v['admission'],
                    availability=v['availability'])
                if v.get('factorization_kind')=='conditional_bernoulli_mixture':
                    source=declare_nodewise_correlated_arm_population_v28p2(st,sig,**kwargs)
                elif v.get('factorization_kind','independent_bernoulli')=='independent_bernoulli':
                    source=declare_nodewise_local_arm_population_v28(st,sig,**kwargs)
                else:
                    raise ValueError('Unsupported conditional nodewise factorization')
                lic=r['license'];_keys(lic,('feature_name','covered_nodes',
                    'potential_outcome_exposure_sufficiency','local_covariate_exposure_mean_exchangeability'))
                license=admit_nodewise_adjustment_a5_v28(st,sig,
                    feature_name=lic['feature_name'],covered_nodes=tuple(lic['covered_nodes']),
                    potential_outcome_exposure_sufficiency=Assumption.model_validate(lic['potential_outcome_exposure_sufficiency']),
                    local_covariate_exposure_mean_exchangeability=Assumption.model_validate(lic['local_covariate_exposure_mean_exchangeability']))
                inquiry=ObservationalNodewiseAdjustedEffectsInquiryV28(st,source,assumptions,sig,license,effect)
            else:
                raise ValueError('Unsupported explicit science packet route')
    return FormalQueryBindingV29(a,inquiry)
