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

## 2.1 模型配置与兼容方案

前端在游戏开始前必须允许观赛者为 12 个玩家分别选择模型、人格和 reasoning 展示策略。后端以 provider 能力注册表做兼容层，前端只读取后端暴露的 provider/model/capability 元数据，不硬编码各厂商 API 差异。

### 2.1.1 Provider 注册表

`configs/providers.yaml` 只保存非敏感元数据和环境变量名，不保存 API key。

```yaml
providers:
  openai:
    display_name: OpenAI
    adapter: openai_responses
    base_url_env: OPENAI_BASE_URL
    api_key_env: OPENAI_API_KEY
    models:
      - id: gpt-5.5
        display_name: GPT-5.5
        capabilities:
          structured_output: true
          reasoning_summary: true
          reasoning_content: false
          encrypted_reasoning: true
        defaults:
          temperature: 0.7
          max_output_tokens: 2000
          reasoning_effort: medium
          reasoning_capture: summary
  openai_compatible:
    display_name: OpenAI Compatible
    adapter: openai_chat_compatible
    base_url_env: CUSTOM_OPENAI_BASE_URL
    api_key_env: CUSTOM_OPENAI_API_KEY
    models: []
```

Provider 注册表字段：

```python
class ProviderConfig:
    id: str
    display_name: str
    adapter: ProviderAdapterKind
    base_url_env: str | None
    api_key_env: str
    models: list[ModelCatalogItem]

class ModelCatalogItem:
    id: str
    display_name: str
    capabilities: ModelCapabilities
    defaults: ModelDefaults

class ModelCapabilities:
    structured_output: bool
    json_mode: bool
    tool_calling: bool
    reasoning_summary: bool
    reasoning_content: bool
    encrypted_reasoning: bool
    reasoning_effort: bool
    max_context_tokens: int | None

class ModelDefaults:
    temperature: float | None
    top_p: float | None
    max_output_tokens: int
    reasoning_effort: str | None
    reasoning_capture: str
```

### 2.1.2 玩家模型配置

每个玩家在创建游戏前都必须有独立 `ModelConfig`。同一局中 12 个玩家可以使用不同 provider 和 model。

```python
class ModelConfig:
    provider_id: str
    model_id: str
    display_name: str
    persona: str | None
    temperature: float | None
    top_p: float | None
    max_output_tokens: int
    timeout_seconds: int
    retry_limit: int
    reasoning: ReasoningConfig

class ReasoningConfig:
    enabled: bool
    effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None
    capture: Literal["off", "summary", "full", "usage_only", "auto"]
    show_to_observer: bool
    show_to_self: bool
    persist_raw_response: bool
```

### 2.1.3 启动前校验

创建游戏前，后端必须执行配置校验：

- 12 个玩家均已配置 provider 和 model。
- provider 已注册且 adapter 存在。
- provider 对应 API key 环境变量存在；前端只显示“已配置/未配置”，不显示密钥。
- reasoning 设置不得超过模型能力：例如不支持 `reasoning_summary` 的模型不能强制 `capture: summary`。
- 若模型不支持结构化输出，adapter 必须启用 JSON prompt + parser 重试策略。
- 每个玩家配置落入运行限制：超时、重试次数、`max_output_tokens` 不超过系统上限。

校验结果返回给前端：

```python
class SetupValidationResult:
    ok: bool
    errors: list[SetupValidationIssue]
    warnings: list[SetupValidationIssue]

class SetupValidationIssue:
    player_id: int | None
    provider_id: str | None
    model_id: str | None
    code: str
    message: str
```

### 2.1.4 Adapter 兼容策略

所有 provider adapter 向上暴露同一个接口：

```python
class ProviderAdapter:
    async def generate(self, request: LLMRequest) -> LLMResponse: ...

class LLMRequest:
    provider_id: str
    model_id: str
    messages: list[LLMMessage]
    output_schema: dict
    temperature: float | None
    top_p: float | None
    max_output_tokens: int
    reasoning: ReasoningConfig
    timeout_seconds: int

class LLMResponse:
    text: str
    parsed_json: dict | None
    reasoning_trace: ReasoningTrace | None
    usage: TokenUsage
    raw_ref: str | None
```

Adapter 责任：

- 把统一 `LLMRequest` 转成 provider 原生 API 参数。
- 优先使用 provider 原生结构化输出；不支持时使用 JSON prompt 并交给 parser 校验。
- 按 provider 能力采集 `reasoning_trace`。
- 归一化错误、超时、限流和 token usage。
- 不在 adapter 中实现游戏规则。

前端只操作 `ModelConfig` 和 catalog 元数据，不直接理解 OpenAI、Claude、Gemini、DeepSeek、Qwen 的请求差异。

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
│   │       │   ├── providers.py  # provider/model catalog API
│   │       │   ├── setup.py      # 创建游戏前配置校验 API
│   │       │   └── ws.py         # WebSocket 路由
│   │       ├── config/
│   │       │   ├── settings.py   # 环境变量与运行配置
│   │       │   ├── loader.py     # YAML 配置加载
│   │       │   └── providers.py  # provider/model catalog
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
│   │       │   ├── registry.py   # adapter 注册与能力匹配
│   │       │   └── reasoning.py  # reasoning_trace 归一化
│   │       ├── services/
│   │       │   ├── setup_service.py # 模型配置校验
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
    vote_state: VoteState | None
    sheriff_election: SheriffElectionState | None
    death_queue: list[DeathRecord]
    public_memory: list[int]       # event_id list
    private_memory: dict[int, list[int]]
    wolf_memory: list[int]
```

Agent 不作为常驻会话进程存在。系统只在玩家轮到行动时构造一次 `AgentInvocation`，读取该玩家可见事件和必要记忆，调用模型生成动作，写入事件后释放运行上下文。

### 4.2.1 GameSetupConfig

```python
class GameSetupConfig:
    players: list[PlayerSetupConfig]  # 长度固定为 12
    runtime: RuntimeConfig

class PlayerSetupConfig:
    player_id: int                    # 1..12
    display_name: str | None
    model_config: ModelConfig
```

`GameSetupConfig` 是 `POST /api/games` 的核心输入。角色分配仍由后端按固定 12 人规则处理，前端只配置每个座位使用哪个模型和 reasoning 策略。

### 4.3 NightActionSet

```python
class NightActionSet:
    round_no: int
    guard_target: int | None
    wolf_kill_target: int
    witch_save_used: bool
    witch_poison_target: int | None
    seer_check_target: int | None
```

`wolf_kill_target` 必须有值。狼人击杀阶段没有合法输出时，系统按 `rule.md` 默认动作在合法存活好人中随机选择。

### 4.4 VoteState

```python
class VoteState:
    candidates: list[int] | None   # None 表示可投任意存活玩家
    excluded_voters: list[int]     # 平票重投时为平票候选人
    ballots: dict[int, int | Literal["abstain"]]
    vote_weights: dict[int, float]
    is_revote: bool
```

白天放逐投票中，普通玩家票权为 `1.0`，警长票权为 `1.5`。平票重投时，只有非平票候选人可在平票候选人中投票。

### 4.5 SheriffElectionState

```python
class SheriffElectionState:
    candidates: list[int]
    withdrawn: list[int]
    ballots: dict[int, int]
    is_revote: bool
```

警长竞选只在第一天发生。只有未上警且存活玩家参与警长投票；重投仍平票时，本局无警长。

### 4.6 DeathRecord

```python
class DeathRecord:
    player_id: int
    timing: Literal["night", "day"]
    round_no: int
    causes: list[DeathCause]
    can_trigger_death_skill: bool
    has_last_words: bool
```

死亡队列按 `rule.md` 处理：同批死亡按玩家编号从小到大；死亡触发技能造成的新死亡追加到队列尾部。警长死亡时，在死亡处理流程中额外生成警徽移交或撕毁动作。

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
→ FIRST_DAY_SHERIFF_GATE / NIGHT_DEATH_FLOW
→ SHERIFF_ELECTION      # 仅第一夜后、死亡技能和遗言前
→ SHERIFF_SPEECH
→ SHERIFF_VOTE
→ SHERIFF_RESULT
  ├─ highest single vote → DEATH_SKILL
  ├─ first tie → SHERIFF_SPEECH → SHERIFF_VOTE → SHERIFF_RESULT
  └─ revote tie → DEATH_SKILL   # 本局无警长
→ DEATH_SKILL
→ SHERIFF_TRANSFER
→ LAST_WORDS
→ WIN_CHECK
→ DISCUSS_ORDER
→ DISCUSS
→ VOTE
→ VOTE_RESULT
  ├─ highest single vote → EXILE
  ├─ all abstain → NO_ELIMINATION
  └─ tie → TIE_SPEECH → TIE_VOTE → VOTE_RESULT
       ├─ highest single vote → EXILE
       └─ tie / all abstain → NO_ELIMINATION
→ DEATH_SKILL
→ SHERIFF_TRANSFER
→ LAST_WORDS
→ WIN_CHECK
→ NIGHT_BEGIN / GAME_END
```

白天任意允许自爆的发言窗口中，狼人可触发：

```text
SHERIFF_SPEECH / DISCUSS / TIE_SPEECH
→ SELF_DESTRUCT
→ DEATH_SKILL
→ SHERIFF_TRANSFER
→ LAST_WORDS
→ DAY_ABORTED
→ WIN_CHECK
→ NIGHT_BEGIN / GAME_END
```

阶段说明：

- `DAWN`：公布夜间死亡玩家编号，不公布死因和身份；夜间真实死因只进入观赛者日志和系统日志。
- `FIRST_DAY_SHERIFF_GATE`：第一夜之后先进入警长竞选；第二夜及之后跳过警长竞选，直接进入夜间死亡处理。
- `SHERIFF_ELECTION`：所有玩家选择是否上警；上警玩家进入候选列表。
- `SHERIFF_SPEECH`：上警玩家或警长平票候选人按系统指定顺序发言，可退水。
- `SHERIFF_VOTE`：未上警且存活玩家投票；最高票当选警长。
- `SHERIFF_RESULT`：警长投票平票时，平票候选人再次发言并由未上警玩家重投；重投仍平票则本局无警长。
- `DISCUSS_ORDER`：警长决定白天发言顺序的起点和方向；无警长时由系统确定。
- `VOTE_RESULT`：最高票放逐；全员弃票进入 `NO_ELIMINATION`；最高票平票进入 `TIE_SPEECH`。
- `TIE_SPEECH`：只有平票候选人发言，仍允许狼人自爆。
- `TIE_VOTE`：非平票候选人在平票候选人中重新投票；重投仍平票进入 `NO_ELIMINATION`。
- `DEATH_SKILL`：按死亡队列执行猎人开枪等死亡触发技能，技能造成的新死亡追加到队列尾部。
- `SHERIFF_TRANSFER`：死亡队列中若包含警长，则该玩家选择移交警徽给 1 名存活玩家或撕毁警徽；默认动作为撕毁警徽。
- `LAST_WORDS`：按 `rule.md` 判断遗言资格；第一夜死亡、白天放逐、白天自爆和白天技能死亡有遗言，第二夜及之后夜死无遗言。白狼王自爆时，白狼王先发表遗言，被带走者随后发表遗言。
- `DAY_ABORTED`：自爆后当前白天阶段终止，不再继续未完成的发言或投票。

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
- 警长：第一夜死讯公布后、死亡技能和遗言处理前竞选；未上警玩家投票；警长票权 `1.5`；死亡时可移交警徽或撕毁警徽。
- 女巫：可自救，不能同夜双药，解药用完后失去刀口信息。
- 守卫：可空守，可自守，不可连续两晚守同一人。
- 同守同救：目标死亡。
- 猎人：被毒不能开枪。
- 普通狼人：白天自爆不能带人；自爆后有遗言，当前白天结束。
- 白狼王：白天自爆可带走 1 名存活玩家；白狼王和被带走者立即进入白天死亡处理，二者都有遗言；遗言和死亡技能处理完毕后当前白天结束。
- 自爆动作：普通狼人 `target` 必须为 `null`；白狼王 `target` 必须是 1 名存活玩家。
- 遗言：第一夜死亡有遗言；第二夜及之后夜死无遗言；白天死亡有遗言；先死亡技能再遗言。
- 夜间结算同时满足狼人屠边和狼人全灭时，狼人优先胜利。

## 8. LLM Agent 设计

### 8.1 Agent 输入

每次调用模型时，只传入该玩家可见信息。未轮到行动的玩家不调用模型，不接收实时推送，也不在后台持续推理。

- 自己的身份、阵营、存活状态。
- 公共事件摘要。
- 自己的私有事件。
- 狼人玩家额外获得狼人阵营事件。
- 当前阶段允许动作和 JSON schema。

观赛者信息、其他玩家私有信息、真实死因不得进入普通 Agent prompt。

### 8.2 Agent 调用生命周期

```text
IDLE
→ BUILD_VISIBLE_CONTEXT
→ CALL_MODEL
→ PARSE_OUTPUT
→ VALIDATE_ACTION
→ WRITE_EVENTS
→ IDLE
```

执行约束：

- `IDLE`：玩家模型不运行、不持有活跃会话，不会持续读取新日志。
- `BUILD_VISIBLE_CONTEXT`：引擎按当前阶段和玩家身份，从事件流派生可见上下文。
- `CALL_MODEL`：LLM adapter 发起一次 API 调用；调用参数包含模型、reasoning 设置、输出 schema 和超时。
- `PARSE_OUTPUT`：解析公开动作、公开发言和 provider 返回的 `reasoning_trace`。
- `VALIDATE_ACTION`：非法动作按 `rule.md` 重试，超过上限使用默认动作。
- `WRITE_EVENTS`：公开发言、动作、私有结果和推理摘要分别写入不同 visibility 的事件。

Agent 的长期记忆不来自常驻对话，而来自事件流派生：

- 公共记忆：所有公共事件摘要。
- 私有记忆：玩家自己的身份、查验、药品、守护、是否可开枪等私有事件。
- 狼人阵营记忆：狼人同伴、夜间讨论和最终刀口。
- 推理记忆：默认不注入下一次 prompt；仅 provider 明确要求延续的加密 reasoning item 可作为不可展示续接材料传回同一 provider。

### 8.3 Agent 输出

所有模型输出必须是 JSON。动作类型以 `rule.md` 第 9 节为准。

投票示例：

```json
{
  "action": "vote",
  "target": 7
}
```

发言和动作分离：

- `speech` 动作的 `content` 是公开文本，会进入公共日志。
- `action` 是系统动作，会被校验和执行。
- 每次模型调用只允许输出当前阶段要求的动作；投票不能附带额外发言。
- 模型的推理摘要不会进入公共发言。

## 9. Reasoning Trace

不同 provider 对“思考内容”的支持不同。系统不要求、也不假设所有模型都能返回完整原始思维链；统一归一化为 `reasoning_trace`，用于观赛、调试和回放。

```python
class ReasoningTrace:
    mode: Literal["off", "hidden", "summary", "full", "encrypted", "usage_only", "self_explanation"]
    provider: str
    model: str
    player_id: int
    phase: Phase
    action: str
    content: str | None
    token_count: int | None
    encrypted_ref: str | None
    raw_ref: str | None
```

### 9.1 Provider 适配策略

| Provider 能力 | 归一化 mode | 展示策略 |
| --- | --- | --- |
| 官方 reasoning summary / thinking summary | `summary` | 前端展示为“推理摘要” |
| 官方返回可读 reasoning_content / thinking text | `full` | 前端展示为“模型返回思考”，并标注 provider |
| 官方返回 encrypted reasoning item | `encrypted` | 不展示正文，只保存引用，用于同 provider 后续请求 |
| 只返回 reasoning token 用量 | `usage_only` | 前端只显示推理 token 数和耗时 |
| 不支持思考输出 | `off` | 前端显示“该模型未提供思考内容” |
| 普通模型按提示生成解释 | `self_explanation` | 作为“自我解释”展示，不标记为真实内部思维 |

处理原则：

- OpenAI reasoning models：使用 Responses API 的 `reasoning.effort` 控制推理强度；如模型支持 `reasoning.summary`，优先保存 summary。原始 reasoning tokens 不可见；encrypted reasoning 只用于续接，不展示正文。
- Claude / Gemini：若 API 返回 thinking summary 或 thought parts，则保存为 `summary` 或 `full`；若只提供预算、签名或加密思考材料，则按 `encrypted` 或 `usage_only` 处理。
- DeepSeek / Qwen 等 OpenAI-compatible reasoning 模型：若响应包含 `reasoning_content`，保存为 `full`；若没有该字段，不通过 prompt 伪造真实思考。
- 普通 chat 模型：不伪装真实思考；如需观赛解释，可追加一个结构化 `self_explanation` 字段或二次摘要调用，并明确标记为“模型自述解释”。

### 9.2 存储与可见性

`reasoning_trace` 只对观赛者和对应玩家可见，不进入公共记忆，也不进入其他玩家 prompt。

事件写入规则：

- 公开发言写入 `speech` 事件，visibility 包含 `public`。
- 动作写入对应动作事件，按规则决定 public / observer / player / wolves。
- 推理摘要写入 `reasoning_trace` 事件，visibility 为 `observer` 和 `player:{id}`。
- 原始 provider 响应写入对象存储或本地文件，事件只保存 `raw_ref`。
- `encrypted_ref` 只可被 LLM adapter 读取，用于后续同 provider 请求；前端不展示。

前端展示：

- 玩家卡片显示最近一次调用状态：`idle` / `thinking` / `speaking` / `acted` / `error`。
- 推理面板默认折叠，展示 provider、model、mode、token_count、耗时和内容。
- `summary`、`full`、`self_explanation` 用不同标签区分，避免把自我解释误认为真实思维链。
- `encrypted` 只显示“已保存加密推理上下文”；`usage_only` 只显示 token 用量。

### 9.3 调用配置

每个玩家模型配置增加 reasoning 选项：

```yaml
reasoning:
  enabled: true
  effort: medium        # provider 支持时生效
  capture: summary      # off / summary / full / usage_only / auto
  show_to_observer: true
  show_to_self: true
  persist_raw_response: true
```

`capture: auto` 的优先级：

1. provider 官方 reasoning summary。
2. provider 官方可读 reasoning content。
3. reasoning token usage。
4. `off`。

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
- `agent_invocation_start`
- `agent_invocation_end`
- `speech`
- `vote`
- `vote_result`
- `tie_speech`
- `tie_vote`
- `no_elimination`
- `exile`
- `night_action`
- `night_resolution`
- `death`
- `death_skill`
- `last_words`
- `sheriff_election`
- `sheriff_result`
- `sheriff_transfer`
- `self_destruct`
- `reasoning_trace`
- `game_end`
- `mvp_result`

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
| `GET` | `/api/providers` | 获取 provider/model catalog 和能力元数据 |
| `POST` | `/api/setup/validate` | 校验 12 个玩家的模型配置 |

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

- `Setup`：为 12 个座位分别选择 provider、model、人格、temperature、超时、重试次数、reasoning effort 和 reasoning capture，并在开始前执行兼容性校验。
- `Game`：实时观战，显示玩家身份、存活状态、发言、投票、夜间行动和推理摘要。
- `History`：读取日志并回放。

核心组件：

- 模型配置表：12 行玩家座位，每行独立 provider/model/reasoning 配置，支持复制配置到全部座位。
- Provider 状态：显示 provider API key 是否已在后端环境中配置，禁止在前端输入或展示密钥。
- 能力提示：根据 catalog 标记模型是否支持结构化输出、reasoning summary、reasoning_content、encrypted reasoning。
- 启动校验面板：展示 `/api/setup/validate` 返回的错误和警告，错误未解决时不能开始游戏。
- 玩家座位区：12 个固定座位。
- 中央事件流：展示当前阶段、发言、投票、死亡、遗言。
- 夜间面板：观赛者可见夜间行动和结算。
- 推理面板：展示 `reasoning_trace`，默认折叠，并区分 `summary`、`full`、`self_explanation`、`usage_only`、`encrypted`。
- 调用状态：玩家卡片显示 `idle`、`thinking`、`speaking`、`acted`、`error`，体现模型只在轮到行动时被调用。
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
