import re

from gtts.tokenizer import Tokenizer, tokenizer_cases, pre_processors
from gtts.utils import _clean_tokens, _len, _minimize


class PreProcessor:
    GOOGLE_TTS_MAX_CHARS = 100  # Max characters the Google TTS API takes at a time

    def __init__(
            self,
            pre_processor_funcs=(
                    pre_processors.tone_marks,
                    pre_processors.end_of_line,
                    pre_processors.abbreviations,
                    pre_processors.word_sub,
            ),
            tokenizer_funcs=(
                    tokenizer_cases.tone_marks,
                    tokenizer_cases.period_comma,
                    tokenizer_cases.colon,
                    tokenizer_cases.other_punctuation,
            ),
            flags=re.IGNORECASE
    ):
        self.pre_processor_funcs = pre_processor_funcs
        self.tokenizer_func = Tokenizer(tokenizer_funcs, flags).run

    def run(self, text):
        text = self._pre_process(text)
        tokens = self._tokenize(text)
        return tokens

    def _pre_process(self, text):
        from tts import log

        # Pre-clean
        text = text.strip()

        # Apply pre-processors
        for pp in self.pre_processor_funcs:
            log.debug("pre-processing: %s", pp)
            text = pp(text)

        return text

    def _tokenize(self, text):
        from tts import log

        if _len(text) <= self.GOOGLE_TTS_MAX_CHARS:
            return _clean_tokens([text])

        # Tokenize
        log.debug("tokenizing: %s", self.tokenizer_func)
        tokens = self.tokenizer_func(text)

        # Clean
        tokens = _clean_tokens(tokens)

        # Minimize
        min_tokens = []
        for t in tokens:
            min_tokens += _minimize(t, " ", self.GOOGLE_TTS_MAX_CHARS)

        # Filter empty tokens, post-minimize
        min_tokens = [t for t in min_tokens if t]

        return min_tokens
