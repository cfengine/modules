This module enables the running of shell commands based on input from the Mission-Portal's build page or `cfbs input`.

Internally these commands are ran using the `"useshell"`-promise based on the `condition`-variable. 

**Note:**
The commands are dispatched with root-privilege (uid=0) and a timeout-window of 300 seconds.

---

**Usage:**

* `command` - The command to run.

* `condition` - Condition for running. Use a class expression (e.g., `linux|bsd`). Defaults to `"any"`

* `ifelapsed` - Number of minutes between assessments. Defaults to 5 minutes.

E.g.
```json
...
{
"command": "echo \"Hello World\"",
"condition": "linux",
"ifelapsed": "5"
},
...
```
Would echo "Hello world" on every linux device with 5 minute intervals.

---

## Contribute

Feel free to open pull requests to expand this documentation, add features or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://tracker.mender.io/issues/).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
