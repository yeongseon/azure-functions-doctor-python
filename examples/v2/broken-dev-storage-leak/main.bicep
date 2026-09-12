resource funcApp 'Microsoft.Web/sites@2023-12-01' = {
  name: 'func-app'
  location: 'koreacentral'
  properties: {
    siteConfig: {
      appSettings: [
        { name: 'AzureWebJobsStorage', value: 'UseDevelopmentStorage=true' }
      ]
    }
  }
}
