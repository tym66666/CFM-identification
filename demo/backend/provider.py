"""One explicit model call with the tested JSON transport; no hidden retries."""
from urllib.parse import urlparse
from .runtime import identification_modules

PROVIDERS = {
    'longcat': {'model': 'LongCat-2.5', 'base_url': 'https://api.longcat.chat/openai/v1', 'thinking': 'disabled'},
    'deepseek': {'model': 'deepseek-v4-flash', 'base_url': 'https://newapi.sufe.edu.cn/v1', 'thinking': 'enabled'},
}


def make_provider(*, model, base_url, api_key=None, timeout=300, thinking=None,
                  max_tokens=16384, observer=None):
    identification_modules()
    if thinking is None and urlparse(base_url).hostname == 'api.longcat.chat':
        thinking = 'disabled'
    from cfm_id_llm.providers.final_content_observer import FinalContentObservedChatProvider
    return FinalContentObservedChatProvider(model=model, base_url=base_url, api_key=api_key,
        timeout=timeout, max_stream_seconds=timeout, max_tokens=max_tokens,
        stream=False, thinking=thinking, json_mode=True, allow_json_fence=False,
        require_finish_reason=True, final_content_observer=observer or (lambda text: None))


def generate(provider, request, *, fact=False):
    prompt = request['request'] if fact else request
    return provider.generate_json(system_prompt=prompt['system' if fact else 'system_prompt'],
                                  user_prompt=prompt['user' if fact else 'user_prompt'])
