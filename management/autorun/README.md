This module enables autorun functionality so you can add policy files to `services/autorun` and tag bundles with `autorun` causing them to be automatically discovered and run.

A policy file you add to `services/autorun` could look like this:

```cfengine3
bundle agent my_example
{
  meta:
    "tags"
      slist => { "autorun" };
  reports:
    "Hello, world!"
}
```

With autorun enabled, the policy file would be parsed, and the bundle evaluated without editing any of your existing files / policy.

It uses the augments file to achieve this, it is the same as editing your `def.json` file like this:

```json
{
  "classes": {
    "services_autorun": ["any"]
  }
}
```
