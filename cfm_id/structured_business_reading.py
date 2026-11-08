"""Explicit, opt-in Responses reader bound to one public business bundle.

Schema validation and source binding are mandatory; they do not approve
business meaning or scientific assumptions. No identification is run here.
The caller supplies credentials/consent/budget and controls any persistence.
"""
from copy import deepcopy
import json

from cfm_id_llm.providers.openai_responses import OpenAICompatibleResponsesProvider
from . import question_bound_assignment as contract
from .fixed_reading_clarity import make_request


class StructuredBusinessReader:
    def __init__(self, bundle, *, model, api_key, base_url, timeout=300.0,
                 max_output_tokens=8192, reasoning_effort='none',
                 transport=None, final_content_observer=None):
        self._bundle=deepcopy(bundle)
        self._system,self._user=make_request(self._bundle)
        schema=json.loads(self._user)['output_schema']
        self.provider=OpenAICompatibleResponsesProvider(model=model,api_key=api_key,
            base_url=base_url,schema=schema,schema_name='business_reading',
            local_validator=lambda raw: contract.resolve_reading(self._bundle,raw),
            timeout=timeout,max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,transport=transport,
            final_content_observer=final_content_observer)

    def request(self):
        """Public request copy, for freezing/auditing before dispatch."""
        return dict(system=self._system,user=self._user)

    def read_once(self):
        raw=self.provider.generate_json(system_prompt=self._system,user_prompt=self._user)
        # Retain actual coordinates, including nulls and comparisons.
        # REVIEW_REQUIRED is not a scientific review or an identification result.
        return contract.preview(self._bundle,raw)

