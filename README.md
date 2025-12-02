# Delfos Multi-Agent System

Multi-agent system for SQL queries and visualization using Microsoft Agent Framework.

## Architecture

```
User Request
     |
     v
+------------------+
|   Coordinator    |  Analyzes intent
+------------------+
     |
     v
+------------------+
|    SQLAgent      |  Generates SQL + executes via MCP
+------------------+
     |
     v
+------------------+
|    Validator     |  Security review
+------------------+
     |
     v
+------------------+
|    VizAgent      |  Creates Power BI charts via MCP
+------------------+
     |
     v
  Response
```

## Quick Start

### 1. Login to Azure

```bash
az login
```

### 2. Configure Environment

```bash
copy .env.example .env
# Edit .env with your Azure AI Foundry endpoint
```

### 3. Install Dependencies

```bash
uv sync --prerelease=allow
```

### 4. Run

```bash
uv run uvicorn src.backend.app:app --reload
```

### 5. Test

Open: http://localhost:8000/docs

## Configuration

Edit `.env`:

```env
AZURE_AI_PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4.1-mini
MCP_SERVER_URL=https://func-mcp-n2z2m7tmh3kvk.azurewebsites.net/mcp
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

## Tech Stack

- Microsoft Agent Framework
- Azure AI Foundry
- FastAPI
- MCP (Model Context Protocol)
- Power BI
