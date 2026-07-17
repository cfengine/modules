This module enables the running of CFEngine policy snippets based on input from Build in Mission Portal or `cfbs input`.

Each policy snippet is saved to a file in `/var/cfengine/state/policy-dispatcher/<number>.cf` and then run with `cf-agent --no-lock --file <file>`, based on the `condition`-variable.

**Note:** The policy snippets are run with root-privilege (uid=0).
Each snippet must be a complete, standalone policy file, containing a `main` bundle (this is what `cf-agent` runs by default).

**Usage:**

- `policy` - The policy snippet to save and run. Must contain a `main` bundle.
- `condition` - Condition for running. Use a class expression (e.g., `linux|bsd`). Defaults to `"any"`
- `ifelapsed` - Number of minutes between assessments. Defaults to 5 minutes.

E.g.

```json
{
  "policy": "bundle agent main { reports: \"Hello World\"; } ",
  "condition": "linux",
  "ifelapsed": "5"
}
```

Would report "Hello World" on every linux device with 5 minute intervals.

## Contribute

Feel free to open pull requests to expand this documentation, add features or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://tracker.mender.io/issues/).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
