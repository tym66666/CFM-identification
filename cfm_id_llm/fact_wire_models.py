"""Closed fact wire model selection for source review and format diagnostics.

These models check wire shape. Native reader parsing and scientific/mathematical
validation remain separate and mandatory; model selection is not route approval.
"""


def model_for(entry):
    if entry.get('reference_format') != 'short_refs':
        return None
    if entry.get('reader_id') is None:
        return None  # Preserve the old advisory model lookup for partial entries.
    from .fact_reading_contracts import contract_for_entry
    contract = contract_for_entry(entry)
    if contract is not None:
        return contract.model
    return None
