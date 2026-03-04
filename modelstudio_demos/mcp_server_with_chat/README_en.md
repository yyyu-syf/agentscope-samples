# FastMCP Server Development Template

> MCP Server development template based on FastMCP framework, quickly develop and deploy to Alibaba Cloud Bailian high-code platform

## 🎉 Features

Core features of this project:

- **🔧 Modular Architecture**: MCP Server code separated into `mcp_server.py`, main program `main.py` handles routing integration
- **💬 Chat API Integration**: New `/process` endpoint supporting Alibaba Cloud Bailian LLM calls and streaming responses
- **🤖 Intelligent Tool Calling**: LLM can automatically identify and call MCP tools (Function Calling)
- **📡 Unified Service Architecture**: FastAPI + FastMCP integration, one service providing both MCP and Chat functionality
- **🔄 Standardized Responses**: Structured streaming responses based on AgentScope ResponseBuilder
- **🌐 CORS Support**: Cross-origin requests supported for frontend integration
- **🎯 Route Optimization**: MCP Server mounted at `/mcp` path, main app provides more endpoints

## ⚡ Quick Start Locally

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Service

```bash
python -m deploy_starter.main
```

### 3. Verify Running

**Health Check:**
```bash
curl http://localhost:8080/health
```

**Test Chat Endpoint (`mode=stock_claim`):**
```bash
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "stock_claim",
    "input": [
      {
        "role": "user",
        "content": [{"type": "text", "text": "我买了600519，帮我看看能不能算索赔金额"}]
      }
    ],
    "session_id": "test-session-001",
    "stream": true
  }'
```

### 4. Recommended: Use MCP Inspector to Verify MCP Server Locally

```bash
npx @modelcontextprotocol/inspector
```
Connect to: `http://localhost:8080/mcp`

![MCP inspector.png](MCP inspector.png)

---

## 🛠️ Stock Claim MCP Tools

The demo exposes two stock-claim tools in `deploy_starter/mcp_server.py`:

1. `get_stock_claim_reference_by_code`
- Input: `stock_code` (6-digit string)
- Output: filing date / benchmark date / benchmark price / status

2. `calculate_stock_claim_compensation`
- Input: stock-claim calculation parameters
- Output: `claim_amount_total`, split amounts, and validation errors

Example definition:

```python
@mcp.tool(
    name="get_stock_claim_reference_by_code",
    description="Query filing and benchmark reference by 6-digit stock code."
)
def get_stock_claim_reference_by_code(
    stock_code: Annotated[str, Field(description="6-digit stock code")]
) -> dict:
    ...
```

`/process` supports request-level prompt routing:
- `mode: "stock_claim"`: inject the stock claim system prompt and guide tool calling.
- `mode: "general"` (default): no stock prompt injection.

**Note**: Configure `DASHSCOPE_API_KEY` to enable chat + function calling.
```bash
export DASHSCOPE_API_KEY='sk-xxxxxx'
```

### One-time DB Copy (from your existing legal_rag DB)

```bash
python -m deploy_starter.scripts.copy_stock_claim_db \
  --src /path/to/source/stock_claim.db
```


---

## 📝 Parameter Description Specification

Use `Annotated` + `Field` to add descriptions for each parameter:

```python
from typing import Annotated, Optional
from pydantic import Field

@mcp.tool(name="calculate_stock_claim_compensation")
def calculate_stock_claim_compensation(
    is_pre_filing_bought: Annotated[bool, Field(description="Bought before filing")],
    avg_buy_price: Annotated[float, Field(description="Average buy price")],
    total_shares: Annotated[float, Field(description="Total shares")],
    pre_benchmark_sold_shares: Annotated[float, Field(description="Sold shares before benchmark")],
    pre_benchmark_avg_sell_price: Annotated[float, Field(description="Average sell price before benchmark")],
) -> dict:
    ...
```

---
## Alibaba Cloud Bailian High-Code Cloud Deployment

### Priority option: Upload code package directly through Alibaba Cloud Bailian high-code console
[Create Application - High-Code Application](https://bailian.console.aliyun.com//app-center?tab=app#/app-center)



### Command line console method for code upload and deployment - Better for quick code modifications and update deployments
#### 1. Install Dependencies

```bash
pip install agentscope-runtime==1.0.0
pip install "agentscope-runtime[deployment]==1.0.0"
```

#### 2. Set Environment Variables

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=...            # Your Alibaba Cloud AccessKey (required)
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=...        # Your Alibaba Cloud SecurityKey (required)

# Optional: If you want to use separate OSS AK/SK, you can set the following (if not set, the above account AK/SK will be used), please ensure the account has OSS read/write permissions
export MODELSTUDIO_WORKSPACE_ID=...               # Your Bailian workspace ID
export OSS_ACCESS_KEY_ID=...
export OSS_ACCESS_KEY_SECRET=...
export OSS_REGION=cn-beijing
```

#### 3. Package and Deploy

##### Method A: Manually Build Wheel File

Ensure your project can be built as a wheel file. You can use setup.py, setup.cfg, or pyproject.toml.

Build wheel file:
```bash
python setup.py bdist_wheel
```

Deploy:
```bash
runtime-fc-deploy \
  --deploy-name [Your application name] \
  --whl-path [Relative path to your wheel file e.g. "/dist/your_app.whl"]
```


For details, please refer to the Alibaba Cloud Bailian high-code deployment documentation: [Alibaba Cloud Bailian High-Code Deployment Documentation](https://bailian.console.aliyun.com/?tab=api#/api/?type=app&url=2983030)

---

## 📋 Project Structure

```
.
├── deploy_starter/
│   ├── main.py          # Main program - FastAPI app entry, integrates Chat and MCP routing
│   ├── mcp_server.py    # MCP Server definition - stock claim tool registration
│   ├── stock_claim_service.py  # Stock claim prompt + domain logic + sqlite store
│   ├── scripts/
│   │   └── copy_stock_claim_db.py  # One-time DB copy utility
│   └── config.yml       # Configuration file
├── requirements.txt     # Dependency list
├── setup.py            # Package configuration (for cloud deployment)
├── README_zh.md        # Chinese documentation
└── README_en.md        # English documentation
```

**Core Files Description:**
- `main.py`: FastAPI main app, provides `/process` endpoint and lifecycle management, mounts MCP Server at `/mcp` path
- `mcp_server.py`: FastMCP server instance, defines stock claim MCP tools
- `stock_claim_service.py`: stock domain logic, reference lookup, compensation calculation, system prompt

---

## 🔧 Configuration

Edit `deploy_starter/config.yml`:

```yaml
# MCP Server Configuration
MCP_SERVER_NAME: "my-mcp-server"
MCP_SERVER_VERSION: "1.0.0"

# Server Configuration
FC_START_HOST: "0.0.0.0"  # For cloud deployment
PORT: 8080
HOST: "127.0.0.1"  # For local development

# Stock claim sqlite path (env STOCK_CLAIM_DB_PATH has higher priority)
STOCK_CLAIM_DB_PATH: "./data/stock_claim/stock_claim.sqlite"

# Alibaba Cloud Bailian API Key (optional, can also use environment variable)
# DASHSCOPE_API_KEY: "sk-xxx"
DASHSCOPE_MODEL_NAME: "qwen-flash"  # LLM model name
```

### DashScope API Configuration

To use Chat and LLM features, you need to configure the Alibaba Cloud Bailian DashScope API KEY:

1. Set `DASHSCOPE_API_KEY` in `deploy_starter/config.yml`:
   ```yaml
   DASHSCOPE_API_KEY: "sk-xxx"
   ```

2. Or set it as an environment variable:
   ```bash
   export DASHSCOPE_API_KEY="sk-xxx"
   ```

---

## 💡 Development Suggestions

### Synchronous vs Asynchronous Tools

- **Synchronous Tools**: Suitable for simple calculations, local operations
  ```python
  @mcp.tool()
  def sync_tool(param: str) -> str:
      return f"processed: {param}"
  ```

- **Asynchronous Tools**: Suitable for API calls, database queries, I/O operations
  ```python
  @mcp.tool()
  async def async_tool(param: str) -> str:
      result = await some_api_call(param)
      return result
  ```

### Tool Naming Conventions

- `name`: Tool name visible to AI (supports Chinese)
- `description`: Detailed explanation of tool purpose, helps AI understand when to call

---

## 🎯 Using in AI Clients

### Claude Desktop

Edit the configuration file `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "my-mcp-server": {
      "command": "python",
      "args": ["-m", "deploy_starter.main"],
      "env": {}
    }
  }
}
```

### Cursor / Cline

Connect to MCP Server URL:
```
http://localhost:8080/mcp
```

### Bailian High-Code Agent Integration

If your application is deployed to Bailian high-code platform, you can directly use the `/process` endpoint for Agent conversations, supporting:
- Natural language interaction
- Automatic tool calling
- Streaming responses
- Complete conversation context management

---

## 📚 API Endpoints

| Endpoint     | Method | Description |
|------------|------|------|
| `/`        | GET | Server information |
| `/health`  | GET | Health check (do not modify) |
| `/process` | POST | Chat endpoint, supports LLM conversation and tool calling (requires DASHSCOPE_API_KEY) |
| `/mcp`     | GET/POST | MCP Server endpoint (Streamable HTTP transport) |

### Chat Endpoint Details

**Request Format:**
```json
{
  "input": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "User message"}
      ]
    }
  ],
  "session_id": "Session ID",
  "stream": true
}
```

**Response Format:**
- Streaming response (SSE), complies with AgentScope ResponseBuilder standard
- Supports multiple message types: `message` (normal answer), `reasoning` (thinking process), `plugin_call` (tool call), `plugin_call_output` (tool output)

**Core Features:**
- ✅ Automatically identify and call MCP tools
- ✅ Support multi-turn conversation context
- ✅ Streaming response, real-time results
- ✅ Transparent tool calling process
