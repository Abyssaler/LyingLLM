# LyingLLM 项目设计

本项目是一个 12 人标准狼人杀模拟与观战系统。系统让 12 个 LLM Agent 按固定规则进行一局狼人杀，人类以观赛者视角查看全局信息、公开发言、投票、夜间行动和模型推理摘要。

规则事实以 [rule.md](./rule.md) 为唯一来源。本文只定义如何把这些规则做成项目。

## 1. 项目目标

- 固定支持 12 人标准局：预言家、女巫、猎人、守卫、4 村民、3 普通狼人、白狼王。
- 后端负责真实状态、规则校验、阶段推进、胜负判定和日志。
- LLM Agent 只负责在自己可见信息范围内发言和行动。
- 前端负责观战、回放、调试和展示模型行为。

非目标：

- 不支持动态人数。
- 不支持自定义角色组合。
- 不让 Agent 自行判定胜负或修改游戏状态。
- 不把观赛者信息泄露给 Agent。

## 2. 技术选型

| 层 | 技术 | 用途 |
| --- | --- | --- |
| 后端 | FastAPI + Pydantic | API、WebSocket、规则模型和状态校验 |
| 引擎 | Python async | 串行推进游戏阶段，调度 LLM 调用 |
| LLM | Provider Adapter | 适配 OpenAI、Claude、Gemini、DeepSeek、Qwen 等接口 |
| 前端 | React + TypeScript + Vite | 观战界面、日志回放、配置模型 |
| 存储 | JSONL/JSON 文件 | 事件日志、快照、原始模型响应引用 |
| 配置 | YAML | provider、模型和运行参数 |

## 3. 代码结构

后端采用 `src` layout。`app` 只作为 FastAPI 启动层，不承载规则、引擎、Agent、LLM、存储等功能代码。可复用业务代码统一放在 `src/lyingllm/` 包内，测试直接面向该包。

```text
LyingLLM/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py              # FastAPI app factory、CORS、路由挂载
│   ├── src/
│   │   └── lyingllm/
│   │       ├── __init__.py
│   │       ├── api/
│   │       │   ├── deps.py       # API 依赖注入
│   │       │   ├── games.py      # REST 路由
│   │       │   └── ws.py         # WebSocket 路由
│   │       ├── config/
│   │       │   ├── settings.py   # 环境变量与运行配置
│   │       │   └── loader.py     # YAML 配置加载
│   │       ├── domain/
│   │       │   ├── models/
│   │       │   │   ├── game.py
│   │       │   │   ├── player.py
│   │       │   │   ├── action.py
│   │       │   │   └── event.py
│   │       │   └── rules/
│   │       │       ├── constants.py   # 从 rule.md 固化出的规则常量
│   │       │       └── validator.py   # 动作合法性校验
│   │       ├── engine/
│   │       │   ├── runner.py     # 游戏主循环
│   │       │   ├── state.py      # GameState 与阶段状态
│   │       │   ├── phases.py     # 阶段推进与转移
│   │       │   ├── resolver.py   # 夜间结算、死亡队列、胜负判定
│   │       │   └── event_bus.py  # 事件广播
│   │       ├── agents/
│   │       │   ├── player_agent.py  # Agent 状态、记忆、可见信息
│   │       │   ├── prompts.py       # Prompt 构造
│   │       │   └── parser.py        # JSON 输出解析
│   │       ├── llm/
│   │       │   ├── client.py
│   │       │   ├── adapters.py
│   │       │   └── reasoning.py  # reasoning_trace 归一化
│   │       ├── services/
│   │       │   ├── game_service.py  # API 用例编排
│   │       │   └── mvp_service.py   # MVP 裁判任务
│   │       └── storage/
│   │           ├── event_log.py     # JSONL 事件流
│   │           └── snapshots.py     # 状态快照
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   └── pyproject.toml
├── configs/
│   ├── providers.yaml
│   └── runtime.yaml
├── frontend/
├── rule.md
└── design.md
```

目录边界：

- `backend/app/`：只允许导入并组装 `lyingllm.*`，不写规则判断、状态变更和 LLM 调用逻辑。
- `lyingllm/domain/`：纯领域模型和规则校验，不依赖 FastAPI、文件系统或 provider SDK。
- `lyingllm/engine/`：唯一可以修改真实游戏状态的层，负责阶段推进和结算。
- `lyingllm/agents/`：只负责可见上下文、prompt、输出解析，不直接改 `GameState`。
- `lyingllm/llm/`：封装不同 provider API，向上暴露统一调用结果。
- `lyingllm/services/`：连接 API、引擎、存储和后台任务，承载应用用例编排。
- `lyingllm/storage/`：负责日志、快照和原始响应引用的持久化。
- `frontend/`：独立前端项目，只通过 REST/WebSocket 访问后端。

## 4. 核心数据模型

### 4.1 Player

```python
class Player:
    id: int                    # 1..12
    role: RoleId               # seer / witch / hunter / guard / villager / werewolf / white_wolf_king
    faction: Faction           # village / wolf
    role_group: RoleGroup      # god / villager / wolf
    alive: bool
    is_sheriff: bool
    model_config: ModelConfig
```

注意：`alive_wolves` 必须统计 `werewolf` 和 `white_wolf_king`，不能只统计普通狼人。

### 4.2 GameState

```python
class GameState:
    game_id: str
    phase: Phase
    round_no: int
    players: list[Player]
    sheriff_id: int | None
    badge_destroyed: bool
    night_actions: NightActionSet
    death_queue: list[DeathRecord]
    public_memory: list[int]       # event_id list
    private_memory: dict[int, list[int]]
    wolf_memory: list[int]
```

### 4.3 NightActionSet

```python
class NightActionSet:
    round_no: int
    guard_target: int | None
    wolf_kill_target: int | None
    witch_save_used: bool
    witch_poison_target: int | None
    seer_check_target: int | None
```

### 4.4 DeathRecord

```python
class DeathRecord:
    player_id: int
    timing: Literal["night", "day"]
    round_no: int
    causes: list[DeathCause]
    can_trigger_death_skill: bool
    has_last_words: bool
```

## 5. 状态机

系统阶段固定，不根据人数或角色组合变化。

```text
SETUP
→ ROLE_ASSIGNMENT
→ NIGHT_BEGIN
→ GUARD_ACTION
→ WOLF_DISCUSS
→ WITCH_ACTION
→ SEER_ACTION
→ NIGHT_RESOLVE
→ DAWN
→ DEATH_SKILL
→ LAST_WORDS
→ WIN_CHECK
→ SHERIFF_ELECTION   # 仅第一天
→ DISCUSS_ORDER
→ DISCUSS
→ VOTE
→ VOTE_RESULT
→ EXILE / NO_ELIMINATION
→ DEATH_SKILL
→ LAST_WORDS
→ WIN_CHECK
→ NIGHT_BEGIN / GAME_END
```

白天任意允许自爆的发言窗口中，狼人可触发：

```text
DISCUSS / SHERIFF_ELECTION / TIE_SPEECH
→ SELF_DESTRUCT
→ DEATH_SKILL
→ LAST_WORDS
→ WIN_CHECK
→ NIGHT_BEGIN / GAME_END
```

## 6. 引擎职责

引擎是唯一可以修改游戏真实状态的模块。

每个阶段执行流程：

1. 根据 `GameState.phase` 生成当前可行动玩家列表。
2. 为每个行动玩家构造可见上下文。
3. 调用 LLM 或使用系统默认动作。
4. 解析 JSON 输出。
5. 使用 `lyingllm.domain.rules.validator` 校验动作是否合法。
6. 记录事件。
7. 更新状态或进入下一阶段。

所有动作失败都走统一策略：

- 解析失败：要求重试。
- 非法动作：说明原因并重试。
- 超时或达到重试上限：使用 `rule.md` 中定义的默认动作。

## 7. 规则实现边界

规则常量来自 `rule.md` 的“系统实现常量”。

实现时需要特别固定以下口径：

- 狼人阵营角色：`werewolf`、`white_wolf_king`。
- 神职角色：`seer`、`witch`、`hunter`、`guard`。
- 村民角色：`villager`。
- 胜负：好人胜为所有狼人阵营出局；狼人胜为所有神职出局或所有村民出局。
- 夜间顺序：守卫 → 狼人 → 女巫 → 预言家。
- 投票：得票最高者放逐，弃票只进入票形日志。
- 平票重投仍平票：无人出局。
- 女巫：可自救，不能同夜双药，解药用完后失去刀口信息。
- 守卫：可空守，可自守，不可连续两晚守同一人。
- 同守同救：目标死亡。
- 猎人：被毒不能开枪。
- 白狼王：白天自爆可带走一人，之后直接入夜。
- 遗言：第一夜死亡有遗言；第二夜起夜死无遗言；白天死亡有遗言；先死亡技能再遗言。
- 夜间结算同时满足狼人屠边和狼人全灭时，狼人优先胜利。

## 8. LLM Agent 设计

### 8.1 Agent 输入

每次调用模型时，只传入该玩家可见信息：

- 自己的身份、阵营、存活状态。
- 公共事件摘要。
- 自己的私有事件。
- 狼人玩家额外获得狼人阵营事件。
- 当前阶段允许动作和 JSON schema。

观赛者信息、其他玩家私有信息、真实死因不得进入普通 Agent prompt。

### 8.2 Agent 输出

所有模型输出必须是 JSON。动作类型以 `rule.md` 第 9 节为准。

示例：

```json
{
  "action": "vote",
  "target": 7,
  "speech": "7号的警徽流和发言逻辑对不上，我投7号。"
}
```

发言和动作分离：

- `speech` 是公开文本，会进入公共日志。
- `action` 是系统动作，会被校验和执行。
- 模型的推理摘要不会进入公共发言。

## 9. Reasoning Trace

不同 provider 对“思考内容”的支持不同。系统统一归一化为 `reasoning_trace`。

```python
class ReasoningTrace:
    mode: Literal["off", "hidden", "summary", "full", "encrypted", "usage_only", "self_explanation"]
    provider: str
    model: str
    player_id: int
    content: str | None
    token_count: int | None
    raw_ref: str | None
```

处理原则：

- OpenAI reasoning models：优先保存 reasoning summary；encrypted reasoning 只用于后续请求，不展示正文。
- Claude / Gemini：若 API 返回 thought summary 或 thought parts，则保存为 `summary` 或 `full`。
- DeepSeek / Qwen：若返回 `reasoning_content`，保存为 `full`。
- 普通 chat 模型：不伪装真实思考；如需观赛解释，标记为 `self_explanation`。

`reasoning_trace` 只对观赛者和对应玩家可见，不进入公共记忆。

## 10. 日志系统

日志采用单一事件流，所有事件只写一次。

```python
class GameEvent:
    event_id: int
    game_id: str
    round_no: int
    phase: Phase
    event_type: str
    player_id: int | None
    visibility: list[str]       # public / observer / player:{id} / wolves
    data: dict
    raw_response_ref: str | None
    timestamp: str
```

派生视图：

- `public_view`：只包含 `visibility` 中有 `public` 的事件。
- `observer_view`：包含所有事件。
- `player_view(player_id)`：公共事件 + 该玩家私有事件 + 该玩家可见阵营事件。
- `wolf_view`：公共事件 + 狼人阵营事件。

事件类型最少包含：

- `phase_change`
- `speech`
- `vote`
- `vote_result`
- `night_action`
- `night_resolution`
- `death`
- `death_skill`
- `last_words`
- `sheriff_election`
- `sheriff_result`
- `self_destruct`
- `reasoning_trace`
- `game_end`

## 11. API 与 WebSocket

### 11.1 REST API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/api/games` | 创建 12 人固定局 |
| `POST` | `/api/games/{id}/start` | 开始游戏 |
| `POST` | `/api/games/{id}/step` | 单步推进 |
| `POST` | `/api/games/{id}/pause` | 暂停 |
| `POST` | `/api/games/{id}/resume` | 恢复 |
| `POST` | `/api/games/{id}/stop` | 终止 |
| `GET` | `/api/games/{id}` | 获取当前状态 |
| `GET` | `/api/games/{id}/events?after_id=0` | 增量事件 |
| `GET` | `/api/games/{id}/log` | 完整日志 |
| `GET` | `/api/games/{id}/reasoning/{player_id}` | 指定玩家推理摘要 |
| `GET` | `/api/games/{id}/mvp` | MVP 结果 |

### 11.2 WebSocket

连接：

```text
/api/ws/games/{game_id}?last_event_id=0
```

服务端先补发 `event_id > last_event_id` 的事件，再推送实时事件。

## 12. MVP 裁判

MVP 裁判不参与游戏，只在 `GAME_END` 后异步执行。

流程：

1. 游戏结束，立即写入结果并推送 `game_end`。
2. 后台任务读取 observer 日志。
3. 裁判模型只在胜利阵营中选择 MVP。
4. 写入 `mvp_result` 事件。
5. 推送给前端。

MVP 失败不影响游戏结果。

## 13. 前端设计

前端只做观战和调试，不负责规则判定。

页面：

- `Setup`：选择 12 个玩家的模型、人格、是否启用 reasoning 展示。
- `Game`：实时观战，显示玩家身份、存活状态、发言、投票、夜间行动和推理摘要。
- `History`：读取日志并回放。

核心组件：

- 玩家座位区：12 个固定座位。
- 中央事件流：展示当前阶段、发言、投票、死亡、遗言。
- 夜间面板：观赛者可见夜间行动和结算。
- 推理面板：展示 `reasoning_trace`，默认折叠。
- 时间线：按事件回放。

## 14. 开发顺序

建议按以下顺序实现：

1. 固化规则常量和 Pydantic 模型。
2. 实现 GameState、Player、Action、Event。
3. 实现夜间结算和胜负判定的单元测试。
4. 实现状态机主循环。
5. 实现 Agent prompt、parser、validator。
6. 接入一个 OpenAI-compatible provider。
7. 实现日志和 WebSocket。
8. 实现最小前端观战页。
9. 增加 reasoning_trace 和 MVP 裁判。
