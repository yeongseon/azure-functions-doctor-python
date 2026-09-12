# Broken: Flex deployment storage without container or auth

`functionAppConfig.deployment.storage` declares neither a container URL nor
authentication. `check_flex_deployment_storage` warns.
