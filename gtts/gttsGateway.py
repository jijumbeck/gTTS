import base64
import json
import logging
import urllib
import re
import requests

from gtts.utils import _clean_tokens, _len, _minimize, _translate_url
from tts import gTTSError

# Logger
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

class GTTSGateway:
    GOOGLE_TTS_HEADERS = {
        "Referer": "http://translate.google.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/47.0.2526.106 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    }
    GOOGLE_TTS_RPC = "jQ1olc"
    
    def __init__(self):
        self._prepared_requests = []
    
    def translate(self, token, lang, accent, slow):
        self._prepare_rpc(token, lang, accent, slow);
        return self._send_rpc()
    
    def _prepare_rpc(self, token, lang, accent, slow):
        """Created the TTS API the request(s) without sending them.

        Returns:
            list: ``requests.PreparedRequests_``. <https://2.python-requests.org/en/master/api/#requests.PreparedRequest>`_``.
        """
        # TTS API URL
        translate_url = _translate_url(
            tld=accent, path="_/TranslateWebserverUi/data/batchexecute"
        )

        text_parts = token
        log.debug("text_parts: %s", str(text_parts))
        log.debug("text_parts: %i", len(text_parts))
        assert text_parts, "No text to send to TTS API"

        prepared_requests = []
        for idx, part in enumerate(text_parts):
            data = self._package_rpc(part, lang, slow)

            log.debug("data-%i: %s", idx, data)

            # Request
            r = requests.Request(
                method="POST",
                url=translate_url,
                data=data,
                headers=self.GOOGLE_TTS_HEADERS,
            )

            # Prepare request
            prepared_requests.append(r.prepare())

        self._prepared_requests = prepared_requests
        return prepared_requests

    def _package_rpc(self, text, lang, speed):
        parameter = [text, lang, speed, "null"]
        escaped_parameter = json.dumps(parameter, separators=(",", ":"))

        rpc = [[[self.GOOGLE_TTS_RPC, escaped_parameter, None, "generic"]]]
        espaced_rpc = json.dumps(rpc, separators=(",", ":"))
        return "f.req={}&".format(urllib.parse.quote(espaced_rpc))

    def _send_rpc(self, request):
        """Do the TTS API request(s) and stream bytes

        Raises:
            :class:`gTTSError`: When there's an error with the API request.

        """
        # When disabling ssl verify in requests (for proxies and firewalls),
        # urllib3 prints an insecure warning on stdout. We disable that.
        try:
            requests.packages.urllib3.disable_warnings(
                requests.packages.urllib3.exceptions.InsecureRequestWarning
            )
        except:
            pass

        prepared_requests = self._prepared_requests
        for idx, pr in enumerate(prepared_requests):
            try:
                with requests.Session() as s:
                    # Send request
                    r = s.send(
                        request=pr, proxies=urllib.request.getproxies(), verify=False
                    )

                log.debug("headers-%i: %s", idx, r.request.headers)
                log.debug("url-%i: %s", idx, r.request.url)
                log.debug("status-%i: %s", idx, r.status_code)

                r.raise_for_status()
            except requests.exceptions.HTTPError as e:  # pragma: no cover
                # Request successful, bad response
                log.debug(str(e))
                raise gTTSError(tts=self, response=r)
            except requests.exceptions.RequestException as e:  # pragma: no cover
                # Request failed
                log.debug(str(e))
                raise gTTSError(tts=self)

            # Write
            for line in r.iter_lines(chunk_size=1024):
                decoded_line = line.decode("utf-8")
                if "jQ1olc" in decoded_line:
                    audio_search = re.search(r'jQ1olc","\[\\"(.*)\\"]', decoded_line)
                    if audio_search:
                        as_bytes = audio_search.group(1).encode("ascii")
                        yield base64.b64decode(as_bytes)
                    else:
                        # Request successful, good response,
                        # no audio stream in response
                        raise gTTSError(tts=self, response=r)
            log.debug("part-%i created", idx)