# LyingLLM 开发指导手册

本文面向 Codex、Claude Code 等编程智能体，用于按阶段实现 LyingLLM。开发时以 [rule.md](./rule.md) 为规则事实唯一来源，以 [design.md](./design.md) 为架构来源。若两者冲突，先停下并报告冲突，不要自行改规则。

## 0. 开发原则

### 0.1 规则优先级

1. `rule.md` 定义游戏规则、动作合法性、胜负、可见性和默认动作。
2. `design.md` 定义工程结构、模块边界、数据流、日志和前端展示。
3. 代码实现不得引入 `rule.md` 未允许的玩法，例如动态人数、自定义角色、观赛者信息泄露给 Agent、Agent 自行修改状态。

### 0.2 模块边界

- `backend/app/`：FastAPI app factory、CORS、路由挂载。只组装，不写业务规则。
- `lyingllm/domain/`：纯模型、枚举、规则常量、动作校验。不得依赖 FastAPI、文件系统、provider SDK。
- `lyingllm/engine/`：唯一可修改真实 `GameState` 的层。负责阶段推进、夜间结算、死亡队列、胜负判定。
- `lyingllm/agents/`：构造可见上下文、prompt、解析模型输出。不得直接改 `GameState`。
- `lyingllm/llm/`：provider adapter、调用、重试、reasoning_trace 归一化。
- `lyingllm/services/`：API 用例编排，连接 engine、storage、llm。
- `lyingllm/storage/`：JSONL 事件流、快照、原始响应引用。
- `frontend/`：只通过 REST/WebSocket 访问后端，不做规则判定。

### 0.3 Agent 运行模型

12 个大模型玩家不是常驻进程。只有轮到某玩家行动时，系统才：

```text
IDLE
→ BUILD_VISIBLE_CONTEXT
→ CALL_MODEL
→ PARSE_OUTPUT
→ VALIDATE_ACTION
→ WRITE_EVENTS
→ IDLE
```

未轮到行动的玩家不调用模型、不持续读取日志、不后台推理。长期记忆来自事件流派生，不来自常驻对话。

### 0.4 信息隔离

- 公共信息可进入所有存活玩家 prompt。
- 私有信息只进入对应玩家 prompt 和观赛者日志。
- 狼人阵营信息只进入狼人 prompt 和观赛者日志。
- `reasoning_trace` 只对观赛者和对应玩家可见，不进入公共记忆，不进入其他玩家 prompt。
- 夜间真实死因不得进入普通 Agent prompt。

## 1. 目标目录

```text
LyingLLM/
├── backend/
│   ├── app/
│   ├── src/
│   │   └── lyingllm/
│   │       ├── api/
│   │       ├── config/
│   │       ├── domain/
│   │       ├── engine/
│   │       ├── agents/
│   │       ├── llm/
│   │       ├── services/
│   │       └── storage/
│   ├── tests/
│   └── pyproject.toml
├── configs/
├── frontend/
├── rule.md
├── design.md
└── DEVELOPMENT_GUIDE.md
```

如果当前仓库尚未有代码，按本结构创建。已有代码时，优先渐进迁移，避免无关重构。

## 2. 阶段一：项目骨架与基础配置

### 2.1 目标

建立可运行的后端包、测试框架、配置加载和最小 FastAPI 应用。

### 2.2 建议文件

- `backend/pyproject.toml`
- `backend/app/main.py`
- `backend/src/lyingllm/__init__.py`
- `backend/src/lyingllm/config/settings.py`
- `backend/src/lyingllm/config/loader.py`
- `configs/providers.yaml`
- `configs/runtime.yaml`
- `backend/tests/unit/test_imports.py`

### 2.3 实现要求

- 使用 `src` layout。
- 后端可通过 `uvicorn app.main:app` 或等效方式启动。
- 配置支持 YAML 文件和环境变量覆盖。
- API key 只从环境变量读取，不写入日志。

### 2.4 验收标准

- `pytest` 能运行。
- FastAPI `/health` 返回健康状态。
- 导入 `lyingllm` 不触发 provider 初始化或网络请求。

## 3. 阶段二：领域模型与规则常量

### 3.1 目标

把 `rule.md` 固化为 Pydantic 模型、枚举和常量。此阶段不实现主循环。

### 3.2 建议文件

- `domain/models/player.py`
- `domain/models/game.py`
- `domain/models/action.py`
- `domain/models/event.py`
- `domain/rules/constants.py`
- `domain/rules/roles.py`

### 3.3 必须建模

- `RoleId`: `seer`, `witch`, `hunter`, `guard`, `villager`, `werewolf`, `white_wolf_king`
- `Faction`: `village`, `wolf`
- `RoleGroup`: `god`, `villager`, `wolf`
- `Phase`: 覆盖设计中的所有阶段。
- `Player`
- `GameState`
- `NightActionSet`
- `VoteState`
- `SheriffElectionState`
- `DeathRecord`
- `GameEvent`
- `ReasoningTrace`

### 3.4 规则常量

常量必须直接覆盖：

- 12 人固定角色数量。
- 狼人阵营角色包含普通狼人和白狼王。
- 神职角色为预言家、女巫、猎人、守卫。
- 胜负：好人胜为所有狼人阵营出局；狼人胜为所有神职出局或所有村民出局。
- 夜间顺序：守卫、狼人、女巫、预言家。
- 警长票权 `1.5`。
- 平票重投仍平票无人出局。
- 女巫可自救、不能同夜双药、解药用完后失去刀口信息。
- 守卫可空守、可自守、不可连续守同一人。
- 同守同救目标死亡。
- 被毒猎人不能开枪。
- 第一夜死亡有遗言，第二夜及之后夜死无遗言，白天死亡有遗言。
- 夜间同时满足狼人屠边和狼人全灭时狼人优先胜利。

### 3.5 验收标准

- `alive_wolves` 统计包含 `white_wolf_king`。
- `NightActionSet.wolf_kill_target` 必填。
- 所有模型可 JSON 序列化和反序列化。
- 单元测试覆盖角色数量、阵营分组、胜负计数基础函数。

## 4. 阶段三：动作 schema 与合法性校验

### 4.1 目标

实现所有 Agent 动作解析和校验。模型输出不能直接执行，必须先过 parser 和 validator。

### 4.2 建议文件

- `domain/models/action.py`
- `domain/rules/validator.py`
- `agents/parser.py`
- `backend/tests/unit/test_action_validator.py`
- `backend/tests/unit/test_parser.py`

### 4.3 动作类型

必须支持：

- `guard`: `target: player_id | null`
- `wolf_vote_kill`: `target: alive_player_id`, `reason`
- `witch`: `use_save: bool`, `poison_target: alive_player_id | null`
- `seer`: `target: alive_player_id`
- `speech`: `content`
- `vote`: `target: alive_player_id | abstain`
- `hunter_shoot`: `target: alive_player_id | null`
- `sheriff_transfer`: `target: alive_player_id | tear_badge`
- `self_destruct`: `target: alive_player_id | null`

### 4.4 校验重点

- 预言家不能查验已出局玩家，不能查验自己。
- 女巫不能同夜双药；解药使用后后续夜晚无刀口信息。
- 女巫毒药只能命中存活玩家。
- 守卫可空守，可自守，不可连续两晚守同一玩家。
- 狼人击杀必须产生合法目标；非法或超时按默认动作随机合法存活好人。
- 普通狼人自爆 `target` 必须为 `null`。
- 白狼王自爆 `target` 必须是 1 名存活玩家。
- 投票只能投存活玩家或弃票。
- 平票重投只能投平票候选人，且平票候选人不得投票。
- 警长投票只由未上警玩家参与。
- 猎人被毒不能开枪。
- 警徽移交目标必须是存活玩家或 `tear_badge`。

### 4.5 默认动作

超过重试上限使用：

- 守卫：空守。
- 狼人击杀：在合法存活好人中随机选择。
- 女巫：不救、不毒。
- 预言家：在未查验存活玩家中随机选择。
- 发言：空发言。
- 投票：弃票。
- 猎人：不开枪。
- 警徽移交：撕毁警徽。

### 4.6 验收标准

- 每种动作都有合法和非法测试。
- 每种默认动作都有测试。
- parser 只接受结构化 JSON，不从自然语言中猜动作。

## 5. 阶段四：夜间结算与胜负判定

### 5.1 目标

实现最核心的纯规则函数：夜间统一结算、死亡队列、死亡技能资格、遗言资格、胜负判定。

### 5.2 建议文件

- `engine/resolver.py`
- `engine/state.py`
- `engine/phases.py`
- `backend/tests/unit/test_night_resolution.py`
- `backend/tests/unit/test_win_condition.py`
- `backend/tests/unit/test_death_queue.py`

### 5.3 夜间结算输入

```yaml
night_actions:
  guard_target: player_id | null
  wolf_kill_target: player_id
  witch_save_used: true | false
  witch_poison_target: player_id | null
  seer_check_target: player_id | null
```

### 5.4 夜间结算规则

- 狼刀目标被守卫守护时，狼刀死亡被阻止。
- 狼刀目标被女巫解药救起时，狼刀死亡被阻止。
- 同一玩家同时被守卫守护和女巫解药救起，该玩家死亡。
- 女巫毒药命中玩家，该玩家死亡。
- 同一玩家多个死因只产生一次死亡，系统日志记录全部死因。
- 预言家查验结果写入预言家私有信息，不影响死亡结算。

### 5.5 死亡处理

- 同批死亡按玩家编号从小到大处理。
- 死亡触发技能造成的新死亡追加到队列尾部。
- 死亡技能先于遗言。
- 警长死亡时要处理警徽移交或撕毁。
- 白狼王自爆时，白狼王先遗言，被带走者随后遗言。

### 5.6 胜负判定

- `alive_gods == 0`：狼人胜。
- `alive_villagers == 0`：狼人胜。
- `alive_wolves == 0`：好人胜。
- 夜间同一次结算同时满足狼人屠边和狼人全灭时，狼人优先胜利。

### 5.7 验收标准

必须测试：

- 狼刀被守卫挡。
- 狼刀被女巫救。
- 同守同救死亡。
- 毒药杀人。
- 狼刀和毒药同目标只产生一次死亡且多死因。
- 被毒猎人不能开枪。
- 第一夜夜死有遗言。
- 第二夜及之后夜死无遗言。
- 猎人夜晚被狼刀后开枪目标按夜间死亡处理。
- 白天猎人开枪目标按白天死亡处理。
- 夜间狼人屠边和狼人全灭同时满足时狼人胜。

## 6. 阶段五：状态机主循环

### 6.1 目标

实现完整阶段推进，但可先使用 stub agent 或默认动作，不必接真实 LLM。

### 6.2 建议文件

- `engine/runner.py`
- `engine/phases.py`
- `engine/event_bus.py`
- `services/game_service.py`
- `backend/tests/integration/test_game_flow_stub.py`

### 6.3 状态机

实现设计中的阶段：

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
→ SHERIFF_ELECTION
→ SHERIFF_SPEECH
→ SHERIFF_VOTE
→ SHERIFF_RESULT
→ DEATH_SKILL
→ SHERIFF_TRANSFER
→ LAST_WORDS
→ WIN_CHECK
→ DISCUSS_ORDER
→ DISCUSS
→ VOTE
→ VOTE_RESULT
→ TIE_SPEECH / TIE_VOTE / EXILE / NO_ELIMINATION
→ DEATH_SKILL
→ SHERIFF_TRANSFER
→ LAST_WORDS
→ WIN_CHECK
→ NIGHT_BEGIN / GAME_END
```

### 6.4 第一夜特殊顺序

第一夜之后：

1. `DAWN` 公布夜间死亡编号。
2. 进入警长竞选。
3. 警长竞选完成后，再处理死亡技能和遗言。
4. 胜负判定。
5. 未结束则进入白天讨论。

第二夜及之后：

1. `DAWN` 公布夜间死亡编号。
2. 直接处理死亡技能、遗言资格、胜负判定。
3. 未结束则进入白天讨论。

### 6.5 自爆路径

允许窗口：

- `SHERIFF_SPEECH`
- `DISCUSS`
- `TIE_SPEECH`

路径：

```text
SELF_DESTRUCT
→ DEATH_SKILL
→ SHERIFF_TRANSFER
→ LAST_WORDS
→ DAY_ABORTED
→ WIN_CHECK
→ NIGHT_BEGIN / GAME_END
```

### 6.6 验收标准

- stub game 可以从 `SETUP` 运行到 `GAME_END`。
- 每个阶段产生 `phase_change` 事件。
- 自爆终止当前白天，不继续未完成发言或投票。
- 平票重投后仍平票进入 `NO_ELIMINATION`。
- 全员弃票进入 `NO_ELIMINATION`。

## 7. 阶段六：事件日志、快照与可见性视图

### 7.1 目标

实现单一事件流，所有派生视图都从事件流产生。

### 7.2 建议文件

- `storage/event_log.py`
- `storage/snapshots.py`
- `domain/models/event.py`
- `engine/event_bus.py`
- `backend/tests/unit/test_visibility.py`
- `backend/tests/integration/test_event_log.py`

### 7.3 事件结构

```python
class GameEvent:
    event_id: int
    game_id: str
    round_no: int
    phase: Phase
    event_type: str
    player_id: int | None
    visibility: list[str]
    data: dict
    raw_response_ref: str | None
    timestamp: str
```

### 7.4 必须支持的事件类型

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

### 7.5 派生视图

- `public_view`：只包含 `public` 事件。
- `observer_view`：包含所有事件。
- `player_view(player_id)`：公共事件 + 该玩家私有事件 + 该玩家可见阵营事件。
- `wolf_view`：公共事件 + 狼人阵营事件。

### 7.6 验收标准

- 夜间真实死因不出现在 `public_view`。
- 预言家查验只出现在预言家视图和 observer 视图。
- 女巫药品状态只出现在女巫视图和 observer 视图。
- 狼人讨论只出现在狼人视图和 observer 视图。
- `reasoning_trace` 不出现在 public 视图。

## 8. 阶段七：Agent prompt、上下文与模型调用

### 8.1 目标

实现按行动窗口唤醒模型的 Agent 调用链。此阶段可先接 mock adapter，再接真实 provider。

### 8.2 建议文件

- `agents/player_agent.py`
- `agents/prompts.py`
- `agents/parser.py`
- `llm/client.py`
- `llm/adapters.py`
- `llm/reasoning.py`
- `backend/tests/unit/test_visible_context.py`
- `backend/tests/unit/test_reasoning_trace.py`

### 8.3 AgentInvocation

建议模型：

```python
class AgentInvocation:
    game_id: str
    player_id: int
    phase: Phase
    allowed_action: str
    visible_context: dict
    output_schema: dict
    model_config: ModelConfig
    reasoning_config: ReasoningConfig
```

### 8.4 Prompt 要求

Prompt 必须包括：

- 玩家自己的身份、阵营、存活状态。
- 当前阶段和可执行动作。
- 当前动作 JSON schema。
- 可见公共事件摘要。
- 自己私有事件摘要。
- 狼人玩家额外获得狼人阵营事件摘要。
- 明确禁止引用不可见信息。
- 明确只输出 JSON。

Prompt 不得包括：

- 观赛者信息。
- 其他玩家私有信息。
- 夜间真实死因。
- 其他玩家 reasoning_trace。

### 8.5 LLM 调用

每次行动独立调用：

```text
agent_invocation_start
→ provider API call
→ parse action / speech / reasoning_trace
→ validate
→ retry or fallback
→ agent_invocation_end
```

未轮到行动的玩家不得调用模型。

### 8.6 验收标准

- 可见上下文测试覆盖普通村民、预言家、女巫、守卫、猎人、普通狼人、白狼王。
- 同一事件在不同视图中的可见性符合 `rule.md`。
- prompt 中不包含 observer-only 字段。
- 模型输出非法时能重试并 fallback。

## 9. 阶段八：Reasoning Trace

### 9.1 目标

前端可查看模型生成发言和动作前的思考摘要或 provider 返回的思考内容，同时不泄露给其他 Agent。

### 9.2 归一化模型

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

### 9.3 Provider 策略

- OpenAI reasoning models：优先使用 Responses API reasoning summary。原始 reasoning tokens 不可见。Encrypted reasoning 只用于续接，不展示正文。
- Claude / Gemini：若返回 thinking summary 或 thought parts，保存为 `summary` 或 `full`。
- DeepSeek / Qwen 等 OpenAI-compatible reasoning 模型：若包含 `reasoning_content`，保存为 `full`。
- 普通 chat 模型：只允许 `self_explanation`，不得标记为真实内部思维。
- 只返回 token 用量时，使用 `usage_only`。

### 9.4 可见性

- `reasoning_trace` visibility 为 `observer` 和 `player:{id}`。
- 不进入 `public_view`。
- 不进入其他玩家 prompt。
- `encrypted_ref` 只给 LLM adapter 使用，前端不展示。

### 9.5 验收标准

- 每种 `mode` 都有序列化测试。
- `summary` 和 `self_explanation` 前端标签不同。
- `encrypted` 只显示占位信息。
- `usage_only` 显示 token 数和耗时。

## 10. 阶段九：REST API 与 WebSocket

### 10.1 目标

提供创建、启动、推进、暂停、恢复、终止、查询和事件订阅能力。

### 10.2 建议文件

- `api/deps.py`
- `api/games.py`
- `api/ws.py`
- `services/game_service.py`
- `backend/tests/integration/test_api_games.py`
- `backend/tests/integration/test_ws_events.py`

### 10.3 REST API

- `POST /api/games`
- `POST /api/games/{id}/start`
- `POST /api/games/{id}/step`
- `POST /api/games/{id}/pause`
- `POST /api/games/{id}/resume`
- `POST /api/games/{id}/stop`
- `GET /api/games/{id}`
- `GET /api/games/{id}/events?after_id=0`
- `GET /api/games/{id}/log`
- `GET /api/games/{id}/reasoning/{player_id}`
- `GET /api/games/{id}/mvp`

### 10.4 WebSocket

连接：

```text
/api/ws/games/{game_id}?last_event_id=0
```

要求：

- 连接后先补发 `event_id > last_event_id` 的事件。
- 再推送实时事件。
- 推送事件必须尊重客户端视图权限。观赛者可看全部，玩家只能看自己的 player_view。

### 10.5 验收标准

- REST 能创建并 step 一局 stub game。
- WebSocket 断线重连能补发遗漏事件。
- `/reasoning/{player_id}` 不返回其他玩家不可见内容。

## 11. 阶段十：前端观战界面

### 11.1 目标

实现可用的观战与调试界面。前端不做规则判定，只展示后端事件和状态。

### 11.2 建议目录

- `frontend/src/api/client.ts`
- `frontend/src/types/index.ts`
- `frontend/src/store/gameStore.ts`
- `frontend/src/hooks/useGame.ts`
- `frontend/src/pages/Setup.tsx`
- `frontend/src/pages/Game.tsx`
- `frontend/src/pages/History.tsx`
- `frontend/src/components/PlayerCard.tsx`
- `frontend/src/components/CenterStage.tsx`
- `frontend/src/components/NightPanel.tsx`
- `frontend/src/components/ReasoningPanel.tsx`
- `frontend/src/components/Timeline.tsx`
- `frontend/src/components/VotePanel.tsx`

### 11.3 页面

- `Setup`：配置 12 个玩家的 provider、model、人格、reasoning 展示策略。
- `Game`：实时观战，展示玩家身份、存活状态、警长、发言、投票、夜间行动、推理摘要。
- `History`：读取事件日志并回放。

### 11.4 组件要求

- 玩家座位区固定 12 个座位。
- 玩家卡片显示 `idle`、`thinking`、`speaking`、`acted`、`error`。
- 中央事件流显示当前阶段、公开发言、投票、死亡、遗言。
- 夜间面板仅观赛者显示夜间行动和结算。
- 推理面板默认折叠，区分 `summary`、`full`、`self_explanation`、`usage_only`、`encrypted`。
- 时间线可按事件回放。

### 11.5 验收标准

- 前端能创建并观看一局 stub game。
- WebSocket 实时更新玩家状态和事件流。
- 推理面板不会把 `self_explanation` 显示成真实内部思考。
- 移动和桌面布局不重叠，12 个座位可扫描。

## 12. 阶段十一：MVP 裁判

### 12.1 目标

游戏结束后异步选择胜利阵营 MVP，不影响游戏结果。

### 12.2 建议文件

- `services/mvp_service.py`
- `agents/prompts.py`
- `backend/tests/unit/test_mvp_service.py`

### 12.3 流程

1. `GAME_END` 写入并推送。
2. 后台任务读取 observer 日志。
3. 裁判模型只在胜利阵营中选择 MVP。
4. 写入 `mvp_result` 事件。
5. 推送给前端。

### 12.4 验收标准

- MVP 失败不改变 `GAME_END`。
- MVP 候选人只来自胜利阵营。
- `mvp_result` 可通过事件流和 `/mvp` 查询。

## 13. 阶段十二：端到端测试与稳定性

### 13.1 必须覆盖

- 一局完整 stub game 能结束。
- 使用 mock LLM 的完整 game 能结束。
- 所有公开/私有/狼人/观赛者视图隔离正确。
- WebSocket 重连补发正确。
- 非法模型输出会重试并 fallback。
- provider 超时会 fallback。
- `reasoning_trace` 不泄露给其他玩家。
- 原始响应引用可落盘并通过 `raw_ref` 找回。

### 13.2 推荐测试分层

- `unit`：规则函数、validator、parser、visibility、resolver。
- `integration`：engine flow、API、WebSocket、storage。
- `e2e`：前端连接后端，创建、运行、观战、回放。

### 13.3 固定回归用例

至少维护这些命名测试：

- `test_alive_wolves_includes_white_wolf_king`
- `test_guard_blocks_wolf_kill`
- `test_guard_and_witch_save_same_target_dies`
- `test_witch_poison_blocks_hunter_shot`
- `test_first_night_death_has_last_words`
- `test_second_night_death_has_no_last_words`
- `test_night_tie_breaker_wolves_win`
- `test_sheriff_revote_tie_no_sheriff`
- `test_vote_revote_tie_no_elimination`
- `test_normal_werewolf_self_destruct_no_target`
- `test_white_wolf_king_self_destruct_takes_target`
- `test_reasoning_trace_not_public`

## 14. 智能体开发工作流

### 14.1 每次开工前

1. 读取 `rule.md` 和相关 `design.md` 章节。
2. 明确本次只改哪些模块。
3. 先写或更新测试，再实现。
4. 不做无关重构。

### 14.2 实现时

- 优先纯函数和小模块。
- 所有状态变更集中在 `engine/`。
- 所有动作执行前必须通过 validator。
- 事件先写入，再派生视图。
- provider adapter 不应污染领域模型。
- 不在 prompt 中注入 observer-only 内容。

### 14.3 完成时

必须报告：

- 改了哪些文件。
- 本阶段完成了哪些验收项。
- 运行了哪些测试。
- 哪些规则边界仍未实现。

## 15. 禁止事项

- 不要让 Agent 自行判定游戏胜负。
- 不要让 Agent 修改 `GameState`。
- 不要把观赛者信息、真实死因、其他玩家私有信息放进普通 Agent prompt。
- 不要把 `reasoning_trace` 放进公共日志。
- 不要把普通模型的自我解释标成真实内部思维。
- 不要添加动态人数、自定义角色组合或新角色。
- 不要在前端实现规则判定。
- 不要在没有测试的情况下修改夜间结算、死亡队列、胜负判定。

## 16. 推荐实施顺序

1. 项目骨架与配置。
2. 领域模型与规则常量。
3. 动作 schema、parser、validator。
4. 夜间结算、死亡队列、胜负判定。
5. 状态机主循环。
6. 事件日志、快照、可见性视图。
7. Agent prompt、上下文、mock LLM。
8. Reasoning Trace 归一化。
9. REST API 与 WebSocket。
10. 前端观战页。
11. MVP 裁判。
12. 端到端测试与稳定性。

