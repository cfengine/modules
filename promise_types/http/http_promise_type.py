import os
import urllib
import urllib.request

from cfengine import PromiseModule, ValidationError, Result


_SUPPORTED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


class HTTPPromiseModule(PromiseModule):
    def __init__(self):
        super().__init__("http_promise_module", "0.0.1")

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
                raise ValidationError("'headers' must be a string, an slist or a data value with 'name: value' pairs")

        if "data" in attributes:
            data = attributes["data"]
            if type(data) not in (str, dict):
                raise ValidationError("'data' must be a string or a data value")

        if "file" in attributes:
            file_ = attributes["file"]
            if type(file_) != str or not os.path.isabs(file_):
                raise ValidationError("'file' must be an absolute path to a file")


    def evaluate_promise(self, promiser, attributes):
        url = attributes.get("url", promiser)
        method = attributes.get("method", "GET")
        headers = attributes.get("headers", dict())
        data = attributes.get("data")
        target = attributes.get("file")

        if headers and type(headers) != dict:
            if type(headers) == str:
                headers = {key: value for key, value in (line.split(":") for line in headers.splitlines())}
            elif type(headers) == list:
                headers = {key: value for key, value in (line.split(":") for line in headers)}

        if data:
            # must be 'None' or bytes or file object
            # TODO: ASCII?
            data = data.encode("utf-8")
        request = urllib.request.Request(url=url, data=data, method=method, headers=headers)

        try:
            if target:
                # TODO: idempotency!
                # TODO: create directories
                with open(target, "wb") as target_file:
                    with urllib.request.urlopen(request) as url_req:
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
                with urllib.urlopen(request) as url_req:
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
            self.log_info("Successfully executed%s request to '%s'" % ((method + " " if method else ""),
                                                                       url))
        return Result.REPAIRED

if __name__ == "__main__":
    HTTPPromiseModule().start()
