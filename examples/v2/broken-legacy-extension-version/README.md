# Broken: legacy FUNCTIONS_EXTENSION_VERSION

`local.settings.json` pins `~3`; the v3 runtime is out of support.
`check_functions_extension_version` warns and the runtime lifecycle check
fails (v3 is past end-of-support).
