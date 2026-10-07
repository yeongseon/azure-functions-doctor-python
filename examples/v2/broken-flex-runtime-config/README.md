# Broken: unsupported Flex runtime version

`functionAppConfig.runtime` declares python 3.9, which is outside the Flex
Consumption target-analysis matrix (3.10-3.14). `check_flex_runtime_config` fails.
