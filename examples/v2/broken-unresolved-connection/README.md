# Unresolved Binding Connection Finding

This runnable v2 app intentionally references `MyStorage` from a queue trigger
without defining a matching app setting.

```bash
azure-functions-doctor doctor --path examples/v2/broken-unresolved-connection --format sarif --output doctor.sarif
```

Captured from the real CLI:

```text
check_binding_connection_resolution: function_app.py:6
Exit code: 0
```

## Safe resolution

`connection="MyStorage"` is the **name** of an app setting, not a connection string.
The setting's **value** holds the connection details and is where secrets live. Doctor
only checks that a setting with that name (or an identity-based `MyStorage__...` group)
exists; it never prints, validates, or needs the real value.

`local.settings.sample.json` shows a corrected local-only counterpart that uses safe
placeholders (the Azurite shorthand `UseDevelopmentStorage=true`, which contains no
secret). Copy it to `local.settings.json` (which is gitignored; never commit it) in a
scratch copy of this example:

```bash
cp -R examples/v2/broken-unresolved-connection /tmp/connection-fixed
cp /tmp/connection-fixed/local.settings.sample.json /tmp/connection-fixed/local.settings.json
azure-functions-doctor doctor --path /tmp/connection-fixed --profile deploy
```

The `check_binding_connection_resolution` finding disappears. For deployed apps, set the
same setting name in the Function App configuration, using Key Vault references or an
identity-based group (`MyStorage__accountName`) instead of pasting a connection string.
See [Troubleshooting](../../../docs/troubleshooting.md#binding-connection-warning-names-an-unconfigured-setting).
