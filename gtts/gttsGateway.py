import base64
import json
import logging
import urllib
import re
import requests

from gtts.utils import _clean_tokens, _len, _minimize, _translate_url

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
    
    def translate(self, token, lang, accent, slow):
        prepared_request = self._prepare_rpc(token, lang, accent, slow)
        return self._send_rpc(prepared_request)
    
    def _prepare_rpc(self, token, lang, accent, slow):
        """Created the TTS API the request without sending them.

        Returns:
            prepared_request: https://2.python-requests.org/en/master/api/#requests.PreparedRequest>.
        """
        # TTS API URL
        translate_url = _translate_url(
            tld=accent, path="_/TranslateWebserverUi/data/batchexecute"
        )

        data = self._package_rpc(token, lang, slow)

        log.debug("data: %s", data)

        # Request
        r = requests.Request(
            method="POST",
            url=translate_url,
            data=data,
            headers=self.GOOGLE_TTS_HEADERS,
        )

        return r.prepare()

    def _package_rpc(self, text, lang, speed):
        parameter = [text, lang, speed, "null"]
        escaped_parameter = json.dumps(parameter, separators=(",", ":"))

        rpc = [[[self.GOOGLE_TTS_RPC, escaped_parameter, None, "generic"]]]
        espaced_rpc = json.dumps(rpc, separators=(",", ":"))
        return "f.req={}&".format(urllib.parse.quote(espaced_rpc))

    def _send_rpc(self, prepared_request):
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

        
        try:
            with requests.Session() as s:
                # Send request
                r = s.send(
                    request=prepared_request, proxies=urllib.request.getproxies(), verify=False
                )

            log.debug("headers: %s", r.request.headers)
            log.debug("url: %s", r.request.url)
            log.debug("status: %s", r.status_code)

            r.raise_for_status()
        except requests.exceptions.HTTPError as e:  # pragma: no cover
            # Request successful, bad response
            log.debug(str(e))
            raise gttsGatewayError(tts=self, response=r)
        except requests.exceptions.RequestException as e:  # pragma: no cover
            # Request failed
            log.debug(str(e))
            raise gttsGatewayError(tts=self)

        # Write
        for line in r.iter_lines(chunk_size=1024):
            decoded_line = line.decode("utf-8")
            if "jQ1olc" in decoded_line:
                audio_search = re.search(r'jQ1olc","\[\\"(.*)\\"]', decoded_line)
                if audio_search:
                    as_bytes = audio_search.group(1).encode("ascii")
                    return base64.b64decode(as_bytes)
                else:
                    # Request successful, good response,
                    # no audio stream in response
                    raise gttsGatewayError(tts=self, response=r)
                    

class gttsGatewayError(Exception):
    """Exception that uses context to present a meaningful error message"""

    def __init__(self, msg=None, **kwargs):
        self.tts = kwargs.pop("tts", None)
        self.rsp = kwargs.pop("response", None)
        if msg:
            self.msg = msg
        elif self.tts is not None:
            self.msg = self.infer_msg(self.tts, self.rsp)
        else:
            self.msg = None
        super(gttsGatewayError, self).__init__(self.msg)

    def infer_msg(self, tts, rsp=None):
        """Attempt to guess what went wrong by using known
        information (e.g. http response) and observed behaviour

        """
        cause = "Unknown"

        if rsp is None:
            premise = "Failed to connect"

            if tts.tld != "com":
                host = _translate_url(tld=tts.tld)
                cause = "Host '{}' is not reachable".format(host)

        else:
            # rsp should be <requests.Response>
            # http://docs.python-requests.org/en/master/api/
            status = rsp.status_code
            reason = rsp.reason

            premise = "{:d} ({}) from TTS API".format(status, reason)

            if status == 403:
                cause = "Bad token or upstream API changes"
            elif status == 200 and not tts.lang_check:
                cause = (
                    "No audio stream in response. Unsupported language '%s'"
                    % self.tts.lang
                )
            elif status >= 500:
                cause = "Uptream API error. Try again later."

        return "{}. Probable cause: {}".format(premise, cause)