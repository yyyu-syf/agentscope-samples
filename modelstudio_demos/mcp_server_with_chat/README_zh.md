# FastMCP Server 开发模版

> 基于 FastMCP 框架的 MCP Server 开发模版，快速开发并部署到阿里云百炼高代码

## 🎉 特性

本项目核心功能：

- **🔧 模块化架构**: MCP Server 代码分离至 `mcp_server.py`，主程序 `main.py` 负责路由整合
- **💬 Chat API 集成**: 新增 `/process` 端点，支持阿里云百炼 LLM 调用和流式响应
- **🤖 智能工具调用**: LLM 可自动识别并调用 MCP 工具（Function Calling）
- **📡 统一服务架构**: FastAPI + FastMCP 集成，一个服务同时提供 MCP 和 Chat 功能
- **🔄 标准化响应**: 基于 AgentScope ResponseBuilder 的结构化流式响应
- **🌐 CORS 支持**: 支持跨域请求，便于前端集成
- **🎯 路由优化**: MCP Server 挂载至 `/mcp` 路径，主应用提供更多端点

## ⚡ 本地快速开始


### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python -m deploy_starter.main
```

### 3. 验证运行

**健康检查:**
```bash
curl http://localhost:8080/health
```

**测试 Chat 接口（`mode=stock_claim`）:**
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

### 4. 推荐使用MCP Inspector本地先验证MCP server

```bash
npx @modelcontextprotocol/inspector
```
连接地址使用: `http://localhost:8080/mcp`

![MCP inspector.png](MCP inspector.png)

---

## 🛠️ 股票索赔 MCP 工具

当前 Demo 在 `deploy_starter/mcp_server.py` 中提供两个股票索赔工具：

1. `get_stock_claim_reference_by_code`
- 输入：`stock_code`（6位数字字符串）
- 输出：立案日、基准日、基准价、状态等参考信息

2. `calculate_stock_claim_compensation`
- 输入：索赔测算参数
- 输出：`claim_amount_total`、分段金额和校验错误

示例定义：

```python
@mcp.tool(
    name="get_stock_claim_reference_by_code",
    description="根据6位股票代码查询立案与基准参考信息"
)
def get_stock_claim_reference_by_code(
    stock_code: Annotated[str, Field(description="6位股票代码")]
) -> dict:
    ...
```

`/process` 支持按请求路由系统提示词：
- `mode: "stock_claim"`：注入股票索赔系统提示词并引导工具调用。
- `mode: "general"`（默认）：不注入股票索赔提示词。

**注意**: 需要设置 `DASHSCOPE_API_KEY` 才能启用 Chat + 工具调用。
```bash
export DASHSCOPE_API_KEY='sk-xxxxxx'
```

### 一次性导入股票索赔数据库（从现有 legal_rag DB 复制）

```bash
python -m deploy_starter.scripts.copy_stock_claim_db \
  --src /path/to/source/stock_claim.db
```


---

## 📝 参数描述规范

使用 `Annotated` + `Field` 为每个参数添加描述：

```python
from typing import Annotated, Optional
from pydantic import Field

@mcp.tool(name="calculate_stock_claim_compensation")
def calculate_stock_claim_compensation(
    is_pre_filing_bought: Annotated[bool, Field(description="是否立案前买入")],
    avg_buy_price: Annotated[float, Field(description="买入均价")],
    total_shares: Annotated[float, Field(description="买入总股数")],
    pre_benchmark_sold_shares: Annotated[float, Field(description="基准日前卖出股数")],
    pre_benchmark_avg_sell_price: Annotated[float, Field(description="基准日前卖出均价")],
) -> dict:
    ...
```

---
## 阿里云百炼高代码 云端部署

### 优先可以选择阿里云百炼高代码控制台直接上传代码包
[创建应用-高代码应用](https://bailian.console.aliyun.com//app-center?tab=app#/app-center)



### 命令行console方式进行代码上传部署-更适合快速修改代码进行更新部署
#### 1. 安装依赖

```bash
pip install agentscope-runtime==1.0.0
pip install "agentscope-runtime[deployment]==1.0.0"
```

#### 2. 设置环境变量

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=...            # 你的阿里云账号AccessKey（必填）
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=...        # 你的阿里云账号SecurityKey（必填）

# 可选：如果你希望使用单独的 OSS AK/SK，可设置如下（未设置时将使用到上面的账号 AK/SK），请确保账号有 OSS 的读写权限
export MODELSTUDIO_WORKSPACE_ID=...               # 你的百炼业务空间id
export OSS_ACCESS_KEY_ID=...
export OSS_ACCESS_KEY_SECRET=...
export OSS_REGION=cn-beijing
```

#### 3. 打包和部署

##### 方式 A：手动构建 wheel 文件

确保你的项目可以被构建为 wheel 文件。你可以使用 setup.py、setup.cfg 或 pyproject.toml。

构建 wheel 文件：
```bash
python setup.py bdist_wheel
```

部署：
```bash
runtime-fc-deploy \
  --deploy-name [你的应用名称] \
  --whl-path [到你的wheel文件的相对路径 如"/dist/your_app.whl"]
```


具体请查看阿里云百炼高代码部署文档：[阿里云百炼高代码部署文档](https://bailian.console.aliyun.com/?tab=api#/api/?type=app&url=2983030)

---

## 📋 项目结构

```
.
├── deploy_starter/
│   ├── main.py          # 主程序 - FastAPI 应用入口，集成 Chat 和 MCP 路由
│   ├── mcp_server.py    # MCP Server 定义 - 注册股票索赔工具
│   ├── stock_claim_service.py  # 股票索赔提示词 + 领域逻辑 + sqlite 存储
│   ├── scripts/
│   │   └── copy_stock_claim_db.py  # 一次性数据库复制脚本
│   └── config.yml       # 配置文件
├── requirements.txt     # 依赖列表
├── setup.py            # 打包配置（用于云端部署）
├── README_zh.md        # 中文文档
└── README_en.md        # 英文文档
```

**核心文件说明:**
- `main.py`: FastAPI 主应用，提供 `/process` 端点和生命周期管理，将 MCP Server 挂载到 `/mcp` 路径
- `mcp_server.py`: FastMCP 服务器实例，定义股票索赔 MCP 工具
- `stock_claim_service.py`: 股票索赔领域逻辑、参考信息查询、金额计算、系统提示词

---

## 🔧 配置说明

编辑 `deploy_starter/config.yml`:

```yaml
# MCP Server 配置
MCP_SERVER_NAME: "my-mcp-server"
MCP_SERVER_VERSION: "1.0.0"

# 服务器配置
FC_START_HOST: "0.0.0.0"  # 云端部署使用
PORT: 8080
HOST: "127.0.0.1"  # 本地开发使用

# 股票索赔 sqlite 路径（环境变量 STOCK_CLAIM_DB_PATH 优先）
STOCK_CLAIM_DB_PATH: "./data/stock_claim/stock_claim.sqlite"

# 阿里云百炼 API Key（可选，也可以用环境变量）
# DASHSCOPE_API_KEY: "sk-xxx"
DASHSCOPE_MODEL_NAME: "qwen-flash"  # LLM 模型名称
```

### DashScope API 配置

要使用 Chat 和 LLM 功能，需要配置阿里云百炼 DashScope API KEY：

1. 在 `deploy_starter/config.yml` 中设置 `DASHSCOPE_API_KEY`:
   ```yaml
   DASHSCOPE_API_KEY: "sk-xxx"
   ```

2. 或设置为环境变量:
   ```bash
   export DASHSCOPE_API_KEY="sk-xxx"
   ```

---

## 💡 开发建议

### 同步 vs 异步工具

- **同步工具**: 适合简单计算、本地操作
  ```python
  @mcp.tool()
  def sync_tool(param: str) -> str:
      return f"processed: {param}"
  ```

- **异步工具**: 适合 API 调用、数据库查询、I/O 操作
  ```python
  @mcp.tool()
  async def async_tool(param: str) -> str:
      result = await some_api_call(param)
      return result
  ```

### 工具命名规范

- `name`: AI 看到的工具名称（支持中文）
- `description`: 详细说明工具用途，帮助 AI 理解何时调用

---

## 🎯 在 AI 客户端中使用

### Claude Desktop

编辑配置文件 `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

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

连接 MCP Server URL:
```
http://localhost:8080/mcp
```

### 百炼高代码 Agent 集成

如果你的应用部署到百炼高代码，可以直接使用 `/process` 端点进行 Agent 对话，支持：
- 自然语言交互
- 自动工具调用
- 流式响应
- 完整的对话上下文管理

---

## 📚 API 端点

| 端点         | 方法 | 说明 |
|------------|------|------|
| `/`        | GET | 服务器信息 |
| `/health`  | GET | 健康检查（请勿修改） |
| `/process` | POST | Chat 接口，支持 LLM 对话和工具调用（需要 DASHSCOPE_API_KEY） |
| `/mcp`     | GET/POST | MCP Server 端点（Streamable HTTP 传输） |

### Chat 接口详细说明

**请求格式:**
```json
{
  "input": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "用户消息"}
      ]
    }
  ],
  "session_id": "会话ID",
  "stream": true
}
```

**响应格式:**
- 流式响应（SSE），符合 AgentScope ResponseBuilder 标准
- 支持多种消息类型: `message`（普通回答）、`reasoning`（思考过程）、`plugin_call`（工具调用）、`plugin_call_output`（工具输出）

**核心特性:**
- ✅ 自动识别并调用 MCP 工具
- ✅ 支持多轮对话上下文
- ✅ 流式响应，实时返回结果
- ✅ 工具调用过程透明可见
