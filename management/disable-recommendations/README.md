The Masterfiles Policy Framework (MPF) emits recommendations for various settings given the context and role of a host.

For example, when federated reporting is enabled on an Enterprise hub, there is a recommendation to install gnu-parallel.

```
R: CFEngine recommends installing gnu parallel on federated reporting superhubs.
```

These can be useful, but you may want to disable the functionality to quiet your policy runs. This module facilitates disabling all recommendations by defining the `default:cfengine_recommendations_disabled` class. Thus it is an equivalent to editing the augments file (`/var/cfengine/masterfiles/def.json`) to:

```json
{
  "classes": {
    "default:cfengine_recommendations_disabled": {
      "class_expressions": [ "any::" ],
      "comment": "We disabled all recommendations emitted by the MPF to quiet policy output."
    }
  }
}
```
