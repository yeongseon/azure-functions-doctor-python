resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: 'fixture-function-app'
  location: resourceGroup().location
  properties: {
    siteConfig: {
      linuxFxVersion: 'Python|3.9'
    }
  }
}
