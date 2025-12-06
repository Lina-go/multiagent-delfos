# Delfos Multi-Agent System

Multi-agent system for SQL queries and visualization using Microsoft Agent Framework.

## Quick Start

### Option 1: Using Docker (Recommended)

#### 1. Build and Run with Docker Compose

```bash
# Create .env file with your configuration
cp .env.example .env
# Edit .env with your Azure AI Foundry endpoint

# Build and run
docker-compose up --build
```

#### 2. Or Build Docker Image Manually

```bash
# Build the image
docker build -t delfos-multi-agent .

# Run the container
docker run -p 8000:8000 \
  -e AZURE_AI_PROJECT_ENDPOINT=your-endpoint \
  -e AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4o \
  -e MCP_SERVER_URL=your-mcp-url \
  -v $(pwd)/logs:/app/logs \
  delfos-multi-agent
```

### Option 2: Local Development

#### 1. Login to Azure

```bash
az login
```

#### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Azure AI Foundry endpoint
```

#### 3. Install Dependencies

```bash
uv sync --prerelease=allow
```

#### 4. Run

```bash
uv run uvicorn src.app:app --reload
```

#### 5. Test

Open: http://localhost:8000/docs

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```env
AZURE_AI_PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4o
MCP_SERVER_URL=https://func-mcp-n2z2m7tmh3kvk.azurewebsites.net/mcp
MCP_TIMEOUT=60
MCP_SSE_TIMEOUT=45
MCP_CHART_SERVER_URL=https://mcp-chart-server.calmocean-fbbefe3a.westus2.azurecontainerapps.io
LOG_LEVEL=INFO
```

### Azure Authentication

For Docker, you have two options:

1. **Service Principal** (Recommended for production):
   ```bash
   export AZURE_CLIENT_ID=your-client-id
   export AZURE_CLIENT_SECRET=your-client-secret
   export AZURE_TENANT_ID=your-tenant-id
   ```

2. **Mount Azure CLI credentials** (For development):
   ```bash
   docker run -v ~/.azure:/root/.azure:ro ...
   ```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/chat` | POST | Process a chat message |
| `/api/tables` | GET | List database tables |
| `/api/schema/{table}` | GET | Get table schema |

## Example Queries

- "Muestrame el balance por tipo de cuenta"
- "Cuantos clientes hay por tipo?"
- "Show me balance by account type"
- "Bar chart with transactions"

## Docker Usage

### Build Image

```bash
docker build -t delfos-multi-agent .
```

### Run Container

```bash
docker run -d \
  --name delfos-app \
  -p 8000:8000 \
  -e AZURE_AI_PROJECT_ENDPOINT=your-endpoint \
  -e AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4o \
  -e MCP_SERVER_URL=your-mcp-url \
  -v $(pwd)/logs:/app/logs \
  delfos-multi-agent
```

### Using Docker Compose

```bash
# Set environment variables in .env file
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Azure Authentication in Docker

The application uses `DefaultAzureCredential` which tries multiple authentication methods:

1. **Environment Variables** (Recommended for Docker):
   ```bash
   export AZURE_CLIENT_ID=your-client-id
   export AZURE_CLIENT_SECRET=your-client-secret
   export AZURE_TENANT_ID=your-tenant-id
   ```

2. **Azure CLI** (Mount credentials):
   ```bash
   docker run -v ~/.azure:/root/.azure:ro ...
   ```

3. **Managed Identity** (If running on Azure):
   - Automatically detected when running on Azure services

## Tech Stack

- Microsoft Agent Framework
- Azure AI Foundry
- FastAPI
- MCP (Model Context Protocol)
- MCP Chart Server (for chart generation)
- Docker
