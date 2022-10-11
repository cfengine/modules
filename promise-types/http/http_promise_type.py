"""HTTP module for CFEngine"""

import filecmp
import os
import urllib
import urllib.request
import ssl
import json
from contextlib import contextmanager

from cfengine import PromiseModule, ValidationError, Result


_SUPPORTED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}

class FileInfo:
    def __init__(self, target):
        self.target = target
        self.was_repaired = False


class HTTPPromiseModule(PromiseModule):
    def __init__(self, name="http_promise_module", version="1.0.0", **kwargs):
        super().__init__(name, version, **kwargs)

    def validate_promise(self, promiser, attributes):
        if "url" in attributes:
            url = attributes["url"]
            if type(url) != str:
                raise ValidationError("'url' must be a string")
            if not url.startswith(("https://", "http://")):
                raise ValidationError("Only HTTP(S) requests are supported")

        if "method" in attributes:
            method = attributes["method"]
            if type(method) != str:
                raise ValidationError("'method' must be a string")
            if method not in _SUPPORTED_METHODS:
                raise ValidationError("'method' must be one of %s" % ", ".join(_SUPPORTED_METHODS))

        if "headers" in attributes:
            headers = attributes["headers"]
            headers_type = type(headers)
            if headers_type == str:
                headers_lines = headers.splitlines()
                if any(line.count(":") != 1 for line in headers_lines):
                    raise ValidationError("'headers' must be string with 'name: value' pairs on separate lines")
            elif headers_type == list:
                if any(line.count(":") != 1 for line in headers):
                    raise ValidationError("'headers' must be a list of 'name: value' pairs")
            elif headers_type == dict:
                # nothing to check for dict?
                pass
            else:
                raise ValidationError("'headers' must be a string, an slist or a data container" +
                                      " value with 'name: value' pairs")

        if "payload" in attributes:
            payload = attributes["payload"]
            if type(payload) not in (str, dict):
                raise ValidationError("'payload' must be a string or a data container value")

            if type(payload) == str and payload.startswith("@") and not os.path.isabs(payload[1:]):
                raise ValidationError("File-based payload must be an absolute path")

        if "file" in attributes:
            file_ = attributes["file"]
            if type(file_) != str or not os.path.isabs(file_):
                raise ValidationError("'file' must be an absolute path to a file")

        if "insecure" in attributes:
            insecure = attributes["insecure"]
            if type(insecure) != str or insecure not in ("true", "True", "false", "False"):
                raise ValidationError("'insecure' must be either \"true\" or \"false\"")

    @contextmanager
    def target_fh(self, file_info):
        if file_info.target:
            dirname = os.path.dirname(file_info.target)
            os.makedirs(dirname, exist_ok=True)
            temp_file = file_info.target+".cftemp"
            with open(temp_file, "wb") as fh:
                yield fh
            if not os.path.isfile(file_info.target) or not filecmp.cmp(temp_file, file_info.target):
                os.replace(temp_file, file_info.target)
                file_info.was_repaired = True
            else:
                os.remove(temp_file)
        else:
            # this is to do something like API requests where you don't care about the result other than response code
            yield open(os.devnull, "wb")


    def evaluate_promise(self, promiser, attributes):
        url = attributes.get("url", promiser)
        method = attributes.get("method", "GET")
        headers = attributes.get("headers", dict())
        payload = attributes.get("payload")
        target = attributes.get("file")
        insecure = attributes.get("insecure", False)
        result = Result.KEPT

        canonical_promiser = promiser.translate(str.maketrans({char: "_" for char in ("@", "/", ":", "?", "&", "%")}))

        if headers and type(headers) != dict:
            if type(headers) == str:
                headers = {key: value for key, value in (line.split(":") for line in headers.splitlines())}
            elif type(headers) == list:
                headers = {key: value for key, value in (line.split(":") for line in headers)}

        if payload:
            if type(payload) == dict:
                try:
                    payload = json.dumps(payload)
                except TypeError:
                    self.log_error("Failed to convert 'payload' to text representation for request '%s'" % url)
                    return (Result.NOT_KEPT,
                            ["%s_%s_request_failed" % (canonical_promiser, method),
                             "%s_%s_payload_failed" % (canonical_promiser, method),
                             "%s_%s_payload_conversion_failed" % (canonical_promiser, method)])

                if "Content-Type" not in headers:
                    headers["Content-Type"] = "application/json"

            elif payload.startswith("@"):
                path = payload[1:]
                try:
                    # Closed automatically when this variable gets out of
                    # scope. Thank you, Python!
                    payload = open(path, "rb")
                except OSError as e:
                    self.log_error("Failed to open payload file '%s' for request '%s': %s" % (path, url, e))
                    return (Result.NOT_KEPT,
                            ["%s_%s_request_failed" % (canonical_promiser, method),
                             "%s_%s_payload_failed" % (canonical_promiser, method),
                             "%s_%s_payload_file_failed" % (canonical_promiser, method)])

                if "Content-Length" not in headers:
                    headers["Content-Length"] = os.path.getsize(path)

            # must be 'None' or bytes or file object
            if type(payload) == str:
                payload = payload.encode("utf-8")

        request = urllib.request.Request(url=url, data=payload, method=method, headers=headers)

        SSL_context = None
        if insecure:
            # convert to a boolean
            insecure = (insecure.lower() == "true")
            if insecure:
                SSL_context = ssl.SSLContext()
                SSL_context.verify_method = ssl.CERT_NONE

        try:      
            with urllib.request.urlopen(request, context=SSL_context) as url_req:
                if not (200 <= url_req.status < 300):
                    self.log_error("Request for '%s' failed with code %d" % (url, url_req.status))
                    return (Result.NOT_KEPT, ["%s_%s_request_failed" % (canonical_promiser, method)])
                # TODO: log progress when url_req.headers["Content-length"] > REPORTING_THRESHOLD
                file_info = FileInfo(target)
                with self.target_fh(file_info) as target_file:
                    should_read = True
                    while should_read:
                        data = url_req.read(512 * 1024)
                        target_file.write(data)
                        should_read = bool(data)
                if file_info.was_repaired:
                    result = Result.REPAIRED
        except urllib.error.URLError as e:
            self.log_error("Failed to request '%s': %s" % (url, e))
            return (Result.NOT_KEPT, ["%s_%s_request_failed" % (canonical_promiser, method)])
        except OSError as e:
            self.log_error("Failed to store '%s' response to '%s': %s" % (url, target, e))
            return (Result.NOT_KEPT,
                    ["%s_%s_request_failed" % (canonical_promiser, method),
                     "%s_%s_file_failed" % (canonical_promiser, method)])

        if target:
            if result == Result.REPAIRED:
                self.log_info("Saved request response from '%s' to '%s'" % (url, target))
            else:
                self.log_info("No changes in request response from '%s' to '%s'" % (url, target))
        else:
            self.log_info("Successfully executed%s request to '%s'" % ((" " + method if method else ""),
                                                                       url))
        return (result, ["%s_%s_request_done" % (canonical_promiser, method)])

if __name__ == "__main__":
    HTTPPromiseModule().start()
