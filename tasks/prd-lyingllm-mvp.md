# PRD: LyingLLM MVP — 12 人标准狼人杀 LLM 模拟与观战系统

## 1. Introduction / Overview

LyingLLM 是一个 12 人标准狼人杀模拟与观战系统，让 12 个 LLM Agent 按 `rule.md` 中的固定规则进行一整局狼人杀，人类以观赛者视角查看全局信息、公开发言、投票、夜间行动。

本 PRD 聚焦 **MVP（能运行的版本）**：从零开始构建可端到端运行的最小系统，使用 mock LLM 跑通完整游戏流程，再增量接入真实 provider。规则事实以 `rule.md` 为唯一来源，架构以 `design.md` 为来源，开发顺序以 `DEVELOPMENT_GUIDE.md` 为来源。

## 2. Goals

- 后端可加载并暴露 provider/model catalog，支持 mock + 至少一个 OpenAI-compatible adapter。
- 实现 `rule.md` 中所有规则的领域模型、动作校验、夜间结算、死亡队列、胜负判定。
- 实现完整状态机：从 `SETUP` 推进到 `GAME_END`，覆盖警长竞选、白天讨论投票、夜间行动、自爆、平票重投等。
- 使用 mock LLM 可跑通一整局游戏。
- 暴露 REST API + WebSocket 让前端可观战。
- 实现最小观战前端：12 个座位卡片、事件流、夜间面板、推理面板（占位即可）。
- 完整事件流和可见性视图：公共/玩家私有/狼人/观赛者视图严格隔离。

## 3. User Stories

### US-001: 项目骨架
**Description:** 作为开发者，我需要一个 Python 后端骨架以承载所有领域代码。

**Acceptance Criteria:**
- [ ] `backend/pyproject.toml` 定义依赖（FastAPI、Pydantic、PyYAML、pytest 等）
- [ ] `backend/app/main.py` 提供 FastAPI app factory 和 `/health` 接口
- [ ] `backend/src/lyingllm/` 包可被导入，且导入时不发起网络请求
- [ ] `pytest` 能运行（即使是空壳测试）
- [ ] `configs/providers.yaml` 和 `configs/runtime.yaml` 占位文件存在

### US-002: 领域模型与规则常量
**Description:** 作为引擎，我需要 Pydantic 模型与规则常量来表示游戏状态。

**Acceptance Criteria:**
- [ ] 定义 `RoleId`、`Faction`、`RoleGroup`、`Phase` 枚举
- [ ] 定义 `Player`、`GameState`、`NightActionSet`、`VoteState`、`SheriffElectionState`、`DeathRecord`、`GameEvent`、`ReasoningTrace`
- [ ] 定义 `ModelConfig`、`ReasoningConfig`、`ProviderConfig`、`ModelCatalogItem`、`ModelCapabilities`、`GameSetupConfig`
- [ ] 规则常量：12 人固定、狼阵营 = `werewolf` + `white_wolf_king`、神职 = `seer` + `witch` + `hunter` + `guard`
- [ ] 单元测试验证 `alive_wolves` 包含白狼王
- [ ] 所有模型可 JSON 序列化和反序列化

### US-003: 动作 schema 与合法性校验
**Description:** 作为引擎，我需要校验 Agent 输出的所有动作合法性。

**Acceptance Criteria:**
- [ ] `agents/parser.py` 只接受结构化 JSON
- [ ] `domain/rules/validator.py` 覆盖 `guard`、`wolf_vote_kill`、`witch`、`seer`、`speech`、`vote`、`hunter_shoot`、`sheriff_transfer`、`self_destruct`
- [ ] 守卫不能连守同一人；预言家不能查自己/已出局者；女巫不能同夜双药
- [ ] 普通狼人自爆 `target` 必须 `null`；白狼王自爆 `target` 必须存活玩家
- [ ] 默认动作覆盖：守卫空守、狼人随机刀好人、女巫不动、预言家随机查、空发言、弃票、不开枪、撕毁警徽
- [ ] 单元测试覆盖每种动作的合法/非法/默认场景

### US-004: 夜间结算与胜负判定
**Description:** 作为引擎，我需要正确执行夜间结算、死亡队列与胜负判定。

**Acceptance Criteria:**
- [ ] `engine/resolver.py` 实现 `rule.md` 第 7 节夜间结算
- [ ] 同守同救 → 死亡
- [ ] 狼刀 + 守卫 → 阻止；狼刀 + 解药 → 阻止；同守同救 → 死亡
- [ ] 同一玩家多死因只产生一次死亡，但记录全部死因
- [ ] 死亡队列按编号排序，技能死亡追加队尾
- [ ] 胜负判定：`alive_wolves==0` 好人胜；`alive_gods==0` 或 `alive_villagers==0` 狼人胜；夜间狼人屠边和狼人全灭同时满足时狼人优先胜
- [ ] 测试：`test_alive_wolves_includes_white_wolf_king`、`test_guard_blocks_wolf_kill`、`test_guard_and_witch_save_same_target_dies`、`test_witch_poison_blocks_hunter_shot`、`test_first_night_death_has_last_words`、`test_second_night_death_has_no_last_words`、`test_night_tie_breaker_wolves_win`

### US-005: 状态机主循环（stub agent）
**Description:** 作为引擎，我需要从 `SETUP` 推进到 `GAME_END`，使用 stub agent 跑通完整流程。

**Acceptance Criteria:**
- [ ] `engine/runner.py` 实现完整阶段推进
- [ ] 第一夜 → DAWN → 警长竞选 → 死亡技能/遗言 → 白天讨论 → 投票 → 第二夜 ...
- [ ] 自爆路径：DISCUSS / SHERIFF_SPEECH / TIE_SPEECH 中可触发，立即结束当前白天
- [ ] 平票路径：TIE_SPEECH → TIE_VOTE → EXILE / NO_ELIMINATION
- [ ] 全员弃票 → NO_ELIMINATION
- [ ] 警长竞选只在第一天；重投仍平票本局无警长
- [ ] 集成测试：用 stub 跑一局至 GAME_END

### US-006: 事件日志与可见性视图
**Description:** 作为系统，所有信息通过单一事件流流动，派生视图严格隔离。

**Acceptance Criteria:**
- [ ] `storage/event_log.py` 提供 JSONL 事件流
- [ ] 实现 `public_view`、`observer_view`、`player_view(id)`、`wolf_view`
- [ ] 夜间真实死因不进入 `public_view`
- [ ] 预言家查验只在预言家视图与 observer 视图
- [ ] 女巫药品状态只在女巫视图与 observer 视图
- [ ] 狼人讨论只在狼人视图与 observer 视图
- [ ] `reasoning_trace` 不进入 `public_view`
- [ ] 单元测试覆盖各视图隔离

### US-007: Agent prompt 构造与 LLM mock
**Description:** 作为引擎，我需要在轮到玩家行动时构造可见上下文并调用 LLM。

**Acceptance Criteria:**
- [ ] `agents/prompts.py` 按角色构造 prompt，只注入玩家可见信息
- [ ] `agents/player_agent.py` 实现 `IDLE → BUILD_VISIBLE_CONTEXT → CALL_MODEL → PARSE_OUTPUT → VALIDATE_ACTION → WRITE_EVENTS → IDLE`
- [ ] `llm/adapters.py` 包含 `MockAdapter`：返回简单合法的 JSON 动作
- [ ] `llm/registry.py` 按 `provider_id` 找 adapter
- [ ] 集成测试：用 mock adapter 跑一局至 GAME_END

### US-008: REST API + WebSocket
**Description:** 作为前端，我需要 REST 创建/启动游戏并通过 WebSocket 订阅事件流。

**Acceptance Criteria:**
- [ ] `POST /api/games` 接收 `GameSetupConfig` 创建游戏
- [ ] `POST /api/games/{id}/start` 启动后台运行
- [ ] `GET /api/games/{id}` 返回 observer 视角的当前状态
- [ ] `GET /api/games/{id}/events?after_id=0` 增量事件
- [ ] `GET /api/providers` 返回 catalog（不含密钥），仅显示 key 是否已配置
- [ ] `POST /api/setup/validate` 校验 12 玩家配置
- [ ] `WS /api/ws/games/{id}?last_event_id=0` 先补发后实时推送（observer 视角）
- [ ] 集成测试：通过 API 创建并跑完一局

### US-009: 最小观战前端
**Description:** 作为观赛者，我能在浏览器观看一局完整游戏。

**Acceptance Criteria:**
- [ ] React + Vite + TypeScript 项目骨架
- [ ] Setup 页：用 `/api/providers` 渲染 12 个座位的 provider/model 选择器，复制按钮一键填满
- [ ] Setup 页：调用 `/api/setup/validate`，存在 error 时禁用开始按钮
- [ ] Game 页：12 个座位卡片，显示编号、状态（idle/thinking/speaking/acted/error）、是否警长
- [ ] Game 页：中央事件流显示发言、投票、死亡、遗言
- [ ] Game 页：夜间面板显示夜间行动（仅观赛者）
- [ ] Game 页：推理面板（默认折叠，区分 mode）
- [ ] WebSocket 实时推送
- [ ] 浏览器手工验证：从 Setup 到 GAME_END 全流程可观战

### US-010: Reasoning Trace 归一化（基础）
**Description:** 作为观赛者，我能看到模型的推理摘要（若 provider 支持）。

**Acceptance Criteria:**
- [ ] `llm/reasoning.py` 归一化 7 种 mode：`off`、`hidden`、`summary`、`full`、`encrypted`、`usage_only`、`self_explanation`
- [ ] Mock adapter 可以产出 `self_explanation` mode
- [ ] `reasoning_trace` 事件 visibility = `[observer, player:{id}]`
- [ ] 单元测试：`test_reasoning_trace_not_public`

## 4. Functional Requirements

- FR-1: 后端固定支持 12 人标准局，不接受其他人数。
- FR-2: 角色分配由后端按 `rule.md` 1.1 节执行；前端只配置每个座位的模型与 reasoning。
- FR-3: 状态机阶段只能由 `engine/` 修改，agent 不直接修改 `GameState`。
- FR-4: Agent 每次只输出当前阶段允许的 JSON 动作；非法重试 N 次后使用默认动作。
- FR-5: 事件流单一来源；公共/私有/狼人/观赛者视图通过事件 `visibility` 字段过滤产生。
- FR-6: API key 只从环境变量读取，不写入日志、不返回前端。
- FR-7: WebSocket 推送遵循订阅者视角（MVP 默认 observer）。
- FR-8: 默认提供 `MockAdapter`，使整个系统可在无 API key 情况下端到端运行。
- FR-9: `reasoning_trace` 不进入公共视图；`encrypted` 引用只给 adapter 内部使用。
- FR-10: 自爆只能在 `DISCUSS`、`SHERIFF_SPEECH`、`TIE_SPEECH` 中触发；自爆后立即终止当前白天阶段。

## 5. Non-Goals (Out of Scope, MVP)

- 不实现动态人数与自定义角色组合。
- 不实现 MVP 裁判（推到下一阶段）。
- 不接入真实 OpenAI/Claude/Gemini SDK 调用（先靠 OpenAI-compatible HTTP + Mock；真实 SDK 适配可在后续阶段补充）。
- 不实现快照、历史回放页（History 页可推迟）。
- 不实现暂停/恢复的复杂半持久化（先做内存版）。
- 不实现复杂的认证、用户系统、多实例部署。
- 不在前端实现任何规则判定。

## 6. Design Considerations

- 后端目录严格按照 `design.md` 第 3 节：`backend/app/` 只组装、`lyingllm/domain/` 纯领域、`lyingllm/engine/` 唯一可改状态。
- 前端目录按 `DEVELOPMENT_GUIDE.md` 11.2 节。
- UI 简洁：12 个座位环形或网格排列，中央事件流，右侧推理面板。
- 状态颜色：alive=亮、dead=灰、警长=金色徽章。

## 7. Technical Considerations

- Python 3.11+，FastAPI、Pydantic v2、PyYAML、pytest、httpx。
- React 18 + Vite + TypeScript + 简单状态管理（Zustand 或 React Context）。
- 内存事件流够用（单进程 in-memory `EventLog`），同步落盘 JSONL 作为持久化兜底。
- 所有 LLM 调用 `async`，`asyncio.to_thread` 包装阻塞 SDK。
- 用 `pytest-asyncio` 测试异步代码。
- 环境变量 `LYINGLLM_CONFIG_DIR` 指向 `configs/`，默认 `./configs`。

## 8. Success Metrics

- 用 mock adapter，从 `POST /api/games` 到 `game_end` 事件 < 30 秒。
- 端到端测试覆盖：`unit/` ≥ 30 测试用例；`integration/` ≥ 5；至少跑过一局 mock 完整局。
- `pytest backend/` 全绿。
- 浏览器观战页能完整呈现一整局。
- 没有任何 observer-only 字段进入 player prompt。

## 9. Open Questions

- 真实 provider 接入顺序（OpenAI Responses vs Anthropic vs OpenAI-compatible）：MVP 先做 OpenAI-compatible（最通用），其余下一阶段。
- WebSocket 鉴权：MVP 不做，后续按需。
- 历史回放页是否纳入 MVP：当前推迟。
