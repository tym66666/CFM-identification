"""Attach numeric progress evidence after a hard deadline; no response content."""
from pathlib import Path
from .budgeted_process_base import run_slot as prior_run_slot, _read, _save

def run_slot(out,run,seconds=300):
    result=prior_run_slot(out,run,seconds)
    pointer=Path(out)/(run+'_pointer.json')
    if pointer.exists():
        folder=Path(_read(pointer)['folder'])
        meta=_read(folder/'result.json'); progress=folder/'provider_progress.json'
        if meta.get('error_code')=='PROCESS_WALL_DEADLINE' and progress.exists():
            values=_read(progress)
            allowed=('elapsed_seconds','wire_bytes','response_bytes','content_characters','stream_events','http_status','headers_seconds','first_content_seconds')
            safe={k:v for k,v in values.items() if k in allowed and type(v) in (int,float)}
            meta['provider_diagnostics']['last_observed_progress']=safe
            _save(folder/'result.json',meta)
    return result
