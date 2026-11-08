"""Opt-in final-content observation. Never exposes reasoning fields or headers."""
from .openai_chat import OpenAICompatibleChatProvider

class FinalContentObservedChatProvider(OpenAICompatibleChatProvider):
    def __init__(self, *, final_content_observer, **kwargs):
        super().__init__(**kwargs)
        self._final_content_observer = final_content_observer

    def _json_object(self, content):
        if isinstance(content, str):
            safe = content.replace(self.api_key, "[REDACTED]") if self.api_key else content
            try:
                self._final_content_observer(safe)
            except Exception:
                self._fail("FINAL_CONTENT_OBSERVER_FAILED", "Final-content observer failed")
        # Observation never repairs malformed JSON or changes acceptance.
        return super()._json_object(content)

