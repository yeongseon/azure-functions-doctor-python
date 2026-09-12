# Broken: dev-storage emulator connection in deployable infra

`AzureWebJobsStorage=UseDevelopmentStorage=true` ships in a bicep template;
the Azurite emulator is unreachable from Azure. `check_dev_storage_connection` warns.
