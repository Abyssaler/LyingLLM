# LyingLLM 操作手册

## 1. 项目概述

LyingLLM 是一个由 LLM 驱动的狼人杀游戏系统。后端基于 FastAPI 提供 REST API + WebSocket 实时推送，前端基于 React + TypeScript + Vite 提供可视化观战界面。

| 组件 | 技术栈 | 默认端口 |
|------|---------|---------|
| 后端 | Python 3.11+, FastAPI, Pydantic v2, uvicorn | 8000 |
| 前端 | React 19, TypeScript, Vite 8, Zustand, TailwindCSS | 3000 (dev) |

---

## 2. 环境准备

### 2.1 系统要求

- Python >= 3.11
- Node.js >= 18
- npm >= 9
- Git

### 2.2 LLM API 密钥

至少配置一个 LLM 提供商的 API Key：

| 提供商 | 环境变量 | 说明 |
|--------|---------|------|
| OpenAI | `OPENAI_API_KEY` | 必填，默认提供商 |
| Anthropic | `ANTHROPIC_API_KEY` | 可选 |
| DeepSeek | `DEEPSEEK_API_KEY` | 可选 |
| 自定义 | `CUSTOM_PROVIDER_N_API_KEY` 等 | 可选，OpenAI 兼容接口 |

---

## 3. 启动步骤

### 3.1 后端

```bash
cd backend

# 1. 创建虚拟环境（推荐）
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 复制环境变量配置文件
cp .env.example .env
# 编辑 .env，填入至少一个 LLM API Key

# 4. 启动服务
python -m app.main
# 或使用 uvicorn 直接启动：
# uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问：
- API 根路径：http://localhost:8000/
- 健康检查：http://localhost:8000/health
- API 文档：http://localhost:8000/docs

### 3.2 前端

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 开发模式启动（自动代理到后端 8000 端口）
npm run dev
# 访问 http://localhost:3000

# 3. 生产构建
npm run build
# 产出在 dist/ 目录

# 4. 预览生产构建
npm run preview
```

---

## 4. 游戏操作流程

### 4.1 创建游戏

1. 打开前端页面 http://localhost:3000
2. 在配置页面设定游戏参数：
   - **玩家数量**：5-12 人
   - **角色配置**：默认 `classic`（经典狼人杀）
   - **规则配置**：默认 `classic`
   - **启用警长**：勾选后开局会进行警长竞选
   - **启用遗言**：勾选后出局玩家可以说遗言
3. 为每个玩家配置：
   - 名称（标识符）
   - 模型（从 providers.yaml 中的模型列表选择）
   - 角色（留空则自动分配）
   - 性格描述（影响 AI 行为风格）
4. 配置裁判 AI 的 Provider 和 Model
5. 点击 **开始游戏 🚀**

### 4.2 游戏控制

进入游戏页面后，顶部控制栏提供以下操作：

| 操作 | 说明 |
|------|------|
| ⏵ 自动 / ⏸ 手动 | 切换自动推进/手动步进模式 |
| ▶ 下一步 | 手动模式下推进一个阶段（仅手动模式可见） |
| 暂停 | 暂停游戏（仅运行中可见） |
| 继续 | 恢复暂停的游戏 |
| 终止 | 强制终止当前游戏 |
| 🌙 夜间 / ☀️ 白天 | 手动切换日夜视觉模式 |
| 自动切换 | 夜间阶段自动切换视觉模式 |

**自动模式**：每 3 秒自动调用 `/step` 接口推进游戏。
**手动模式**：需要手动点击"下一步"按钮推进。

### 4.3 游戏阶段流转

完整的游戏阶段和自动步进逻辑：

```
WAITING → SHERIFF_ELECTION → NIGHT_BEGIN → WOLF_DISCUSS → NIGHT_ACTIONS
→ DAWN → LAST_WORDS → WIN_CHECK → DISCUSS_ORDER → DISCUSS → VOTE
→ VOTE_RESULT → EXECUTE / NO_ELIMINATION → ON_DEATH_SKILL → WIN_CHECK
→ （循环或 GAME_END）
```

平票处理分支：`VOTE_RESULT → TIE_SPEECH → TIE_VOTE → VOTE_RESULT`（最多重投 `max_revote_rounds` 次）

### 4.4 查看游戏信息

- **左侧/右侧面板**：玩家卡片，显示角色图标、阵营标记、警长标识、存活状态
- **中央区域**：
  - 顶部：当前轮次 + 阶段 + 存活人数
  - 事件日志：最近的阶段事件
  - 底部标签页：发言 / 投票 / 思维
- **底部时间线**：显示所有阶段变化节点

### 4.5 查看历史对局

访问 http://localhost:3000/history 查看所有已创建的游戏列表，点击查看日志（完整/白天/夜间）。

---

## 5. API 接口参考

### 5.1 游戏管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/games` | 创建新游戏 |
| GET | `/api/games` | 列出所有游戏 |
| GET | `/api/games/{id}` | 获取游戏详情 |
| POST | `/api/games/{id}/start` | 开始游戏 |
| POST | `/api/games/{id}/pause` | 暂停游戏 |
| POST | `/api/games/{id}/resume` | 恢复游戏 |
| POST | `/api/games/{id}/stop` | 终止游戏 |
| POST | `/api/games/{id}/step` | 推进一个阶段 |
| POST | `/api/games/{id}/action` | 提交玩家行动 |
| POST | `/api/games/{id}/rerun-action` | 重试上一个行动 |

### 5.2 游戏数据接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/games/{id}/mvp` | 获取 MVP |
| GET | `/api/games/{id}/log` | 获取完整日志 |
| GET | `/api/games/{id}/log/day` | 获取白天日志 |
| GET | `/api/games/{id}/log/night` | 获取夜间日志 |
| GET | `/api/games/{id}/events?after_id=N` | 获取增量事件 |
| GET | `/api/games/{id}/thinking/{player_id}` | 获取玩家思维过程 |

### 5.3 配置接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/configs/roles` | 列出所有角色配置 |
| GET | `/api/configs/roles/{name}` | 获取指定角色配置 |
| GET | `/api/configs/rules` | 列出所有规则配置 |
| GET | `/api/configs/rules/{name}` | 获取指定规则配置 |
| GET | `/api/configs/models` | 获取模型提供商配置 |
| POST | `/api/configs/validate` | 验证配置组合 |

### 5.4 WebSocket

连接地址：`ws://localhost:8000/api/ws/games/{game_id}?last_event_id=0`

连接后可收到实时事件推送，支持断线重连（传入 `last_event_id` 获取增量事件）。

客户端可发送：
- `{"type": "ping"}` → 收到 `{"type": "pong"}`
- `{"type": "subscribe"}` → 收到 `{"type": "subscribed", "game_id": "..."}`

服务端推送事件类型（25 种）：
`game_start`, `game_end`, `game_paused`, `game_resumed`, `game_aborted`, `phase_change`, `state_snapshot`, `sheriff_election`, `sheriff_result`, `night_begin`, `wolf_discuss`, `night_action`, `dawn`, `speech`, `last_words`, `vote`, `vote_result`, `tie_speech`, `tie_vote`, `execute`, `on_death_skill`, `thinking`, `action_retry`, `action_fallback`, `error`

---

## 6. 配置文件说明

### 6.1 目录结构

```
backend/configs/
├── roles/
│   └── classic.yaml      # 角色定义（狼人/村民/预言家/女巫/猎人/守卫）
├── rules/
│   └── classic.yaml      # 规则定义（夜间顺序/投票/胜负条件等）
└── models/
    └── providers.yaml    # LLM 提供商及模型配置
```

### 6.2 环境变量

配置文件路径：`backend/.env`（从 `.env.example` 复制）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_HOST` | `0.0.0.0` | 服务监听地址 |
| `APP_PORT` | `8000` | 服务监听端口 |
| `APP_DEBUG` | `false` | 调试模式（启用 uvicorn reload） |
| `APP_LOG_DIR` | `./logs` | 日志目录 |
| `OPENAI_API_KEY` | - | OpenAI API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI API 地址 |
| `ANTHROPIC_API_KEY` | - | Anthropic API Key |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Anthropic API 地址 |
| `DEEPSEEK_API_KEY` | - | DeepSeek API Key |
| `CUSTOM_PROVIDER_N_*` | - | 自定义提供商（N=1,2,...） |

### 6.3 YAML 配置

**角色配置** (`roles/classic.yaml`)：定义 6 种角色的名称、阵营、技能、提示词等。

**规则配置** (`rules/classic.yaml`)：定义游戏流程规则，关键参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `enable_sheriff` | true | 是否启用警长 |
| `enable_last_words` | true | 是否启用遗言 |
| `enable_wolf_discuss` | true | 狼人是否可以夜间讨论 |
| `voting.type` | majority | 投票类型 |
| `voting.tie_handling` | revote | 平票处理方式 |
| `voting.max_revote_rounds` | 2 | 最大重投轮数 |
| `voting.sheriff_vote_weight` | 1.5 | 警长投票权重 |
| `voting.allow_abstain` | true | 是否允许弃权 |
| `witch_can_self_save` | false | 女巫能否自救 |
| `hunter_can_shoot_on_witch_kill` | true | 猎人被毒死能否开枪 |
| `guard_cannot_guard_same_twice` | true | 守卫不能连续守护同一人 |
| `mvp_include_dead_players` | true | MVP 评选是否包含死亡玩家 |

**模型配置** (`models/providers.yaml`)：定义 LLM 提供商、默认模型、重试策略等。API Key 使用 `${ENV_VAR}` 格式引用环境变量。

---

## 7. 测试

```bash
cd backend

# 运行所有测试
python tests/test_all.py      # 基础模型/角色/内存/解析器测试
python tests/test_engine.py   # 引擎/存储/规则测试

# 类型检查
mypy app/

# 代码检查
ruff check app/
```

```bash
cd frontend

# TypeScript 类型检查
npx tsc --noEmit

# 代码检查
npm run lint

# 生产构建验证
npm run build
```

---

## 8. 故障排查

| 问题 | 原因 | 解决方法 |
|------|------|---------|
| `OPENAI_API_KEY` 报错 | 未设置 API Key | 编辑 `backend/.env` 填入有效 Key |
| WebSocket 连接失败 | 前端代理未配置或后端未启动 | 确保后端运行在 8000 端口，前端 dev server 代理已配置 |
| 游戏卡在某阶段 | LLM 调用超时或失败 | 检查后端日志，确认 API 可达；使用 `/rerun-action` 重试 |
| 前端白屏 | 后端未启动或 API 代理问题 | 先启动后端，再启动前端 dev server |
| Phase transition 报 409 | 阶段转换不合法 | 检查当前阶段是否允许该操作，参考阶段流转图 |
| 游戏自动推进无效 | 自动模式下 API 报错 | 打开浏览器控制台查看网络请求 |