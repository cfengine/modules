"""HTTP module for CFEngine"""

import os
import urllib
import urllib.request
import ssl
import json

from cfengine import PromiseModule, ValidationError, Result


_SUPPORTED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


class HTTPPromiseModule(PromiseModule):
    def __init__(self):
        super().__init__("http_promise_module", "0.0.2")

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


    def evaluate_promise(self, promiser, attributes):
        url = attributes.get("url", promiser)
        method = attributes.get("method", "GET")
        headers = attributes.get("headers", dict())
        payload = attributes.get("payload")
        target = attributes.get("file")
        insecure = attributes.get("insecure", False)

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
                    return Result.NOT_KEPT

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
                    return Result.NOT_KEPT

                if "Content-Lenght" not in headers:
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
            if target:
                # TODO: idempotency!
                # TODO: create directories
                with open(target, "wb") as target_file:
                    with urllib.request.urlopen(request, context=SSL_context) as url_req:
                        if not (200 <= url_req.status <= 300):
                            self.log_error("Request for '%s' failed with code %d" % (url, url_req.status))
                            return Result.NOT_KEPT
                        # TODO: log progress when url_req.headers["Content-length"] > REPORTING_THRESHOLD
                        done = False
                        while not done:
                            data = url_req.read(512 * 1024)
                            target_file.write(data)
                            done = bool(data)
            else:
                with urllib.request.urlopen(request, context=SSL_context) as url_req:
                    if not (200 <= url_req.status <= 300):
                        self.log_error("Request for '%s' failed with code %d" % (url, url_req.status))
                        return Result.NOT_KEPT
                    done = False
                    while not done:
                        data = url_req.read(512 * 1024)
                        done = bool(data)
        except urllib.error.URLError as e:
            self.log_error("Failed to request '%s': %s" % (url, e))
            return Result.NOT_KEPT
        except OSError as e:
            self.log_error("Failed to store '%s' response to '%s': %s" % (url, target, e))
            return Result.NOT_KEPT

        if target:
            self.log_info("Saved request response from '%s' to '%s'" % (url, target))
        else:
            self.log_info("Successfully executed%s request to '%s'" % ((" " + method if method else ""),
                                                                       url))
        return Result.REPAIRED

if __name__ == "__main__":
    HTTPPromiseModule().start()
