"""Same frozen prompts; correct only question-numbering validation."""
from . import business_frozen_reading_base as prior
from . import business_condition_evidence as evidence
from . import business_evidence_entries as entries
from . import business_staged_d1_d2 as staged

from cfm_id.workflows.legacy_network.frozen_reading import make_request


from cfm_id.workflows.legacy_network.frozen_reading import identify


def normalize(bundle,provider,entry,envelope=None):
    s,u=make_request(bundle,entry,envelope)
    return identify(bundle,provider.generate_json(system_prompt=s,user_prompt=u),entry,envelope)
