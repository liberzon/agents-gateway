# Azure Deployment

Deploy Agents Gateway to Azure Container Apps.

## Prerequisites

- Azure CLI installed and logged in
- Azure subscription with Container Apps enabled
- Docker for building images (or use Azure Container Registry build)

## Quick Start

### 1. Create Resource Group

```bash
az group create \
  --name agents-gateway-rg \
  --location eastus
```

### 2. Create Azure Container Registry (Optional)

```bash
az acr create \
  --resource-group agents-gateway-rg \
  --name agentsgatewayacr \
  --sku Basic

# Build and push image
az acr build \
  --registry agentsgatewayacr \
  --image agents-gateway:latest \
  --file Dockerfile .
```

### 3. Deploy with Bicep

```bash
# Deploy infrastructure and application
az deployment group create \
  --resource-group agents-gateway-rg \
  --template-file deploy/azure/container-apps/main.bicep \
  --parameters \
    environment=dev \
    containerImage=agentsgatewayacr.azurecr.io/agents-gateway:latest \
    dbConnectionString="postgresql://user:pass@host:5432/db" \
    tokenEncryptionKey="your-base64-fernet-key"
```

### 4. Get Application URL

```bash
az containerapp show \
  --name agents-gateway-dev \
  --resource-group agents-gateway-rg \
  --query properties.configuration.ingress.fqdn \
  --output tsv
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│              Azure Container Apps                            │
│         (Built-in Ingress + Auto-scaling)                   │
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │    Revision     │    │    Revision     │                 │
│  │  agents-gateway │    │  agents-gateway │                 │
│  └────────┬────────┘    └────────┬────────┘                 │
└───────────┼──────────────────────┼──────────────────────────┘
            │                      │
┌───────────▼──────────────────────▼──────────────────────────┐
│              Azure Database for PostgreSQL                   │
│                     (Flexible Server)                        │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_TOKEN_ENC_KEY` | Yes | Fernet encryption key |
| `QDRANT_URL` | No | Qdrant vector database URL |

### Scaling Configuration

Modify in Bicep template:

```bicep
scale: {
  minReplicas: 2        // Minimum instances
  maxReplicas: 20       // Maximum instances
  rules: [
    {
      name: 'http-scaling'
      http: {
        metadata: {
          concurrentRequests: '50'  // Scale up when requests > 50
        }
      }
    }
  ]
}
```

## Database Setup

### Create Azure Database for PostgreSQL

```bash
# Create PostgreSQL Flexible Server
az postgres flexible-server create \
  --resource-group agents-gateway-rg \
  --name agents-gateway-db \
  --location eastus \
  --admin-user agadmin \
  --admin-password 'YourSecurePassword123!' \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 15

# Create database
az postgres flexible-server db create \
  --resource-group agents-gateway-rg \
  --server-name agents-gateway-db \
  --database-name agents_gateway

# Allow Azure services
az postgres flexible-server firewall-rule create \
  --resource-group agents-gateway-rg \
  --name agents-gateway-db \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

## Costs

Estimated monthly costs (East US):

- **Container Apps (0.5 vCPU, 1GB, 2 replicas)**: ~$30
- **PostgreSQL (Burstable B1ms)**: ~$25
- **Log Analytics**: ~$5-10

Total: ~$60-70/month for development workloads.

## Monitoring

### View Logs

```bash
az containerapp logs show \
  --name agents-gateway-dev \
  --resource-group agents-gateway-rg \
  --follow
```

### View Metrics

```bash
az monitor metrics list \
  --resource /subscriptions/{sub}/resourceGroups/agents-gateway-rg/providers/Microsoft.App/containerApps/agents-gateway-dev \
  --metric "Requests" \
  --interval PT1H
```

## Troubleshooting

### Check revision status

```bash
az containerapp revision list \
  --name agents-gateway-dev \
  --resource-group agents-gateway-rg \
  --output table
```

### Restart application

```bash
az containerapp revision restart \
  --name agents-gateway-dev \
  --resource-group agents-gateway-rg \
  --revision <revision-name>
```

### Update container image

```bash
az containerapp update \
  --name agents-gateway-dev \
  --resource-group agents-gateway-rg \
  --image agentsgatewayacr.azurecr.io/agents-gateway:v2.0.0
```
