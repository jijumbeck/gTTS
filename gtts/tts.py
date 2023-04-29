# -*- coding: utf-8 -*-
import base64
import json
import logging
import re
import urllib

import requests

from gtts.lang import _fallback_deprecated_lang, tts_langs
from gtts.tokenizer import Tokenizer, pre_processors, tokenizer_cases
from gtts.utils import _clean_tokens, _len, _minimize, _translate_url
from pre_process import PreProcessor
from gttsGateway import GTTSGateway


__all__ = ["gTTS", "gTTSError"]

# Logger
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

class gTTS:

    GOOGLE_TTS_MAX_CHARS = 100  # Max characters the Google TTS API takes at a time
    GOOGLE_TTS_HEADERS = {
        "Referer": "http://translate.google.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/47.0.2526.106 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    }
    GOOGLE_TTS_RPC = "jQ1olc"

    def __init__(
        self,
        lang="en",
        accent="com",
        slow=False,
        lang_check=True,
        pre_processor = PreProcessor(),
        gateway = GTTSGateway()
    ):

        # Debug
        for k, v in dict(locals()).items():
            if k == "self":
                continue
            log.debug("%s: %s", k, v)

        # Text

        # Translate URL top-level domain
        self.accent = accent

        # Language
        self.lang_check = lang_check
        self.lang = lang

        if self.lang_check:
            # Fallback lang in case it is deprecated
            self.lang = _fallback_deprecated_lang(lang)

            try:
                langs = tts_langs()
                if self.lang not in langs:
                    raise ValueError("Language not supported: %s" % lang)
            except RuntimeError as e:
                log.debug(str(e), exc_info=True)
                log.warning(str(e))

        self.slow = slow

        # Pre-processors and tokenizer
        self.pre_processor = pre_processor
        self.gateway = gateway

    def stream(self, text):
        """Do the TTS API request(s) and stream bytes

        Raises:
            :class:`gTTSError`: When there's an error with the API request.
        """

        tokens = self.__prepare_text(text)

        for token in tokens:
            yield self.gateway.translate(token, self.lang, self.accent, self.slow)


    def write_to_fp(self, fp, text):
        """Do the TTS API request(s) and write bytes to a file-like object.

        Args:
            fp (file object): Any file-like object to write the ``mp3`` to.

        Raises:
            :class:`gTTSError`: When there's an error with the API request.
            TypeError: When ``fp`` is not a file-like object that takes bytes.

        """

        try:
            for idx, decoded in enumerate(self.stream(text)):
                fp.write(decoded)
                log.debug("part-%i written to %s", idx, fp)
        except (AttributeError, TypeError) as e:
            raise TypeError(
                "'fp' is not a file-like object or it does not take bytes: %s" % str(e)
            )

    def save(self, savefile, text):
        """Do the TTS API request and write result to file.

        Args:
            savefile (string): The path and file name to save the ``mp3`` to.

        Raises:
            :class:`gTTSError`: When there's an error with the API request.

        """
        with open(str(savefile), "wb") as f:
            self.write_to_fp(f, text)
            log.debug("Saved to %s", savefile)

    def __prepare_text(self, text):
        return self.pre_processor.run(text)