# Icon Reference — Azure Service Icons

Vendor (Azure) icon catalog split out of `icons.md` to keep each reference under the harness 300-line cap. Load alongside `icons.md` when drawing Azure-branded nodes.

## Azure Service Icons

Azure brand colour: `#0089D6` (top tile / outer ring). Service-specific accents come from Microsoft's Azure icon set; use them as the inner badge fill so a glance still tells you "this is Azure".

**Template (Azure tile):**
```xml
<!-- Azure tile: outer rounded square in Azure blue, inner badge for the service. -->
<rect x="cx-22" y="cy-22" width="44" height="44" rx="6"
      fill="#0089D6" stroke="none"/>
<rect x="cx-19" y="cy-19" width="38" height="38" rx="4"
      fill="SERVICE_COLOR" stroke="none"/>
<text x="cx" y="cy+5" text-anchor="middle" fill="white"
      font-size="9" font-weight="700" font-family="Helvetica">BADGE</text>
```

### Azure Compute

| Product | Service Color | Badge |
|---------|---------------|-------|
| Azure Functions | `#0062AD` | `Func` |
| Azure App Service | `#0072C6` | `App` |
| Azure Container Apps | `#3F8624` | `ACA` |
| Azure Container Instances | `#0078D4` | `ACI` |
| Azure Kubernetes Service (AKS) | `#326CE5` | `AKS` |
| Azure Virtual Machines | `#0078D4` | `VM` |
| Azure Batch | `#0072C6` | `Batch` |
| Azure Spring Apps | `#6DB33F` | `Spring` |

### Azure Data & Analytics

| Product | Service Color | Badge |
|---------|---------------|-------|
| Azure SQL Database | `#0066A1` | `SQL` |
| Azure Cosmos DB | `#3D7AB3` | `Cosmos` |
| Azure Database for PostgreSQL | `#336791` | `pg` |
| Azure Database for MySQL | `#4479A1` | `MySQL` |
| Azure Synapse Analytics | `#0078D4` | `Syn` |
| Azure Data Factory | `#0078D4` | `ADF` |
| Azure Databricks | `#FF3621` | `Bricks` |
| Azure Stream Analytics | `#0072C6` | `Stream` |
| Azure Data Explorer (Kusto) | `#1E5180` | `Kusto` |
| Azure Cache for Redis | `#DC382D` | `Redis` |

### Azure Storage

| Product | Service Color | Badge |
|---------|---------------|-------|
| Azure Blob Storage | `#0078D4` | `Blob` |
| Azure Queue Storage | `#0078D4` | `Queue` |
| Azure Table Storage | `#0078D4` | `Table` |
| Azure Files | `#0078D4` | `Files` |
| Azure Data Lake Storage Gen2 | `#0078D4` | `Lake` |

### Azure AI

| Product | Service Color | Badge |
|---------|---------------|-------|
| Azure OpenAI Service | `#10A37F` | `AOAI` |
| Azure AI Search (Cognitive Search) | `#0078D4` | `AISrch` |
| Azure AI Foundry | `#742774` | `Foundry` |
| Azure Machine Learning | `#0078D4` | `AML` |
| Azure AI Content Safety | `#107C10` | `Safety` |
| Azure Speech / Translator | `#0078D4` | `Speech` |

### Azure Messaging & Eventing

| Product | Service Color | Badge |
|---------|---------------|-------|
| Azure Service Bus | `#0078D4` | `SB` |
| Azure Event Grid | `#0078D4` | `Grid` |
| Azure Event Hubs | `#0078D4` | `Hubs` |
| Azure Notification Hubs | `#0078D4` | `Notif` |
| Azure SignalR Service | `#0078D4` | `SignalR` |

### Azure Networking & Edge

| Product | Service Color | Badge |
|---------|---------------|-------|
| Azure Front Door | `#0078D4` | `AFD` |
| Azure Application Gateway | `#0078D4` | `AppGW` |
| Azure Load Balancer | `#0078D4` | `LB` |
| Azure API Management | `#1FBA9F` | `APIM` |
| Azure Virtual Network | `#0078D4` | `VNet` |
| Azure Private Link | `#0078D4` | `PL` |
| Azure CDN | `#0078D4` | `CDN` |
| Azure DNS | `#0078D4` | `DNS` |

### Azure Identity & Security

| Product | Service Color | Badge |
|---------|---------------|-------|
| Microsoft Entra ID (Azure AD) | `#0072C6` | `Entra` |
| Azure Key Vault | `#FFB900` | `KV` |
| Azure Sentinel | `#0072C6` | `Sentinel` |
| Microsoft Defender for Cloud | `#0078D4` | `Defender` |

### Azure DevOps & Operations

| Product | Service Color | Badge |
|---------|---------------|-------|
| Azure DevOps Pipelines | `#0078D4` | `Pipelines` |
| GitHub Actions (Azure target) | `#181717` | `GHA` |
| Azure Monitor | `#0078D4` | `Monitor` |
| Application Insights | `#0072C6` | `AppI` |
| Azure Log Analytics | `#0078D4` | `Logs` |

### Azure-specific shapes

For diagrams that need a recognisable "Azure" visual without a service badge — e.g. a region container or a subscription boundary — use a dashed Azure-blue outline:

```xml
<!-- Azure region/subscription container -->
<rect x="x" y="y" width="w" height="h" rx="8"
      fill="#0089D6" fill-opacity="0.04"
      stroke="#0089D6" stroke-width="1.2" stroke-dasharray="6,4"/>
<text x="x+12" y="y+16" fill="#0089D6" font-size="10"
      font-weight="700" letter-spacing="0.06em">AZURE • REGION NAME</text>
```
