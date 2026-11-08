"""Bind study reading independently of changing goals for existing D1/D2 entries.

Binding preserves a candidate, not its scientific truth. No gold labels or
licenses are added, and changing the public history invalidates the envelope.
"""
from copy import deepcopy
import json
from . import business_evidence_entries as entries
from .business_core_pilot_base import canonical_hash
from . import business_d1_submission as d1
from . import business_d2_submission as d2

from cfm_id.workflows.legacy_network.staged_d1_d2 import VERSION


from cfm_id.workflows.legacy_network.staged_d1_d2 import _model


from cfm_id.workflows.legacy_network.staged_d1_d2 import historical_materials


def study_request(bundle,entry):
    _model(entry)
    system,user=entries.base_request(bundle,entry);schema=json.loads(user)['output_schema']
    schema['properties'].pop('questions');schema['required']=['study'];schema.pop('$defs',None)
    materials=historical_materials(bundle,entry);refs=list(materials['source_catalog'])
    props=schema['properties']['study']['properties']
    props['design_sources']['items']={'type':'string','enum':refs}
    for field in ('exposure_source','independence_source'):
        if field in props:props[field]={'anyOf':[{'type':'string','enum':refs},{'type':'null'}]}
    system+='''
本次只返回study，不返回questions。只读取提供的历史研究材料，不处理当前业务目标。
exposure表示历史研究协议声明的分析分组，而不是这次目标限定了多少邻居。邻居使用人数的0、1、2等人数分类用exact_treated_neighbor_count。
历史分组不能推导当前要问的分组，也不表示A5成立。历史来源引用source_catalog；未说明的信息保留未知。
'''
    return system,json.dumps({**materials,'output_schema':schema},ensure_ascii=False)


from cfm_id.workflows.legacy_network.staged_d1_d2 import bind_study


from cfm_id.workflows.legacy_network.staged_d1_d2 import validate_envelope


from cfm_id.workflows.legacy_network.staged_d1_d2 import target_request


from cfm_id.workflows.legacy_network.staged_d1_d2 import compose


from cfm_id.workflows.legacy_network.staged_d1_d2 import identify
