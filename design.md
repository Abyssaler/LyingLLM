# LyingLLM 整体框架设计

## 技术选型

| 层       | 技术                      | 说明                                         |
| -------- | ------------------------- | -------------------------------------------- |
| 后端     | FastAPI + Pydantic        | 异步API、模型验证                            |
| LLM调用  | 多格式适配器              | OpenAI兼容/Claude原生/Token Plan等，统一调度 |
| 前端     | React + TypeScript + Vite | 轻量现代前端                                 |
| 实时通信 | WebSocket (FastAPI原生)   | 游戏过程实时推送                             |
| 配置     | YAML                      | 角色、规则、模型配置                         |
| 日志存储 | JSON 文件                 | 简单可移植，后续可换DB                       |

## 项目结构

```
LyingLLM/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── settings.py          # 全局配置
│   │   │   └── loader.py            # YAML 加载器
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py            # 游戏引擎：主循环、阶段调度
│   │   │   ├── state.py             # 游戏状态机
│   │   │   ├── phase.py             # 阶段定义与转换
│   │   │   └── event_bus.py          # 事件总线（解耦通信）
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── game.py               # 对局模型
│   │   │   ├── player.py            # 玩家模型
│   │   │   ├── role.py              # 角色定义模型
│   │   │   └── event.py             # 事件/日志模型
│   │   ├── roles/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # 角色基类（含技能接口）
│   │   │   ├── werewolf.py
│   │   │   ├── villager.py
│   │   │   ├── seer.py
│   │   │   ├── witch.py
│   │   │   ├── hunter.py
│   │   │   └── guard.py
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Agent 基类（人格+思维+记忆）
│   │   │   ├── prompts.py           # Prompt 模板构建器
│   │   │   ├── parser.py           # 输出解析与校验器
│   │   │   ├── personality.py       # 人格特质定义
│   │   │   └── judge.py             # 裁判 AI（MVP 评选）
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py            # LLM 统一调度客户端
│   │   │   ├── adapter.py           # 多格式适配器（OpenAI/Claude）
│   │   │   ├── retry.py             # 重试与降级策略
│   │   │   └── message.py           # 对话历史管理
│   │   ├── rules/
│   │   │   ├── __init__.py
│   │   │   └── manager.py           # 规则管理器
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   └── game_memory.py       # Agent游戏内记忆（公共+私有）
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   └── game_log.py          # 对局日志持久化
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── game.py              # 对局相关API
│   │       ├── config.py            # 配置相关API
│   │       └── ws.py                # WebSocket 实时推送
│   ├── configs/
│   │   ├── roles/
│   │   │   └── classic.yaml         # 经典角色定义
│   │   ├── rules/
│   │   │   └── classic.yaml         # 经典规则集
│   │   └── models/
│   │       └── providers.yaml       # LLM provider 配置
│   ├── logs/                         # 对局日志目录
│   ├── tests/
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── .env.example                 # 环境变量模板
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── PlayerCard.tsx        # 玩家配置卡片
│   │   │   ├── GameBoard.tsx         # 游戏棋盘
│   │   │   ├── ChatPanel.tsx         # 发言面板
│   │   │   ├── VotePanel.tsx         # 投票面板
│   │   │   ├── ThinkingViewer.tsx    # 思维过程查看器
│   │   │   ├── NightOverlay.tsx      # 夜间视觉模式遮罩
│   │   │   └── CenterStage.tsx       # 中间信息展示区
│   │   ├── pages/
│   │   │   ├── Setup.tsx             # 对局配置页
│   │   │   ├── Game.tsx              # 对局观看页
│   │   │   └── History.tsx           # 历史记录页
│   │   ├── store/
│   │   │   └── gameStore.ts          # Zustand 状态管理
│   │   ├── api/
│   │   │   └── client.ts             # API + WebSocket 客户端
│   │   └── App.tsx
│   ├── package.json
│   └── tsconfig.json
└── README.md
```

## 核心架构

### 1. 游戏引擎 (`core/engine.py`)

引擎是整个系统的调度中心，采用**阶段驱动**的异步循环：

```
Setup → Role Assignment → ┌─ Night Phase ─┐──→ Day Phase ──┐──→ Win Check
                           │  (各角色依次行动) │  (讨论→投票→处决) │       │
                           └────────────────┘───────────────┘───────┘
```

- **Night Phase**: 按优先级收集各角色夜间技能（守卫→狼人协商并确认击杀目标→女巫→预言家），随后由统一结算器计算死亡与技能结果
- **Day Phase**: 通告昨夜信息 → 按指定顺序依次发言 → 投票 → 处决/平票处理
- **Win Check**: 每次死亡结算、处决、死亡触发技能结束后检查胜负条件

#### 1.1 夜间行动收集与结算

夜间阶段区分**行动收集顺序**和**结果结算顺序**。角色在自己的行动窗口内只提交意图，不能直接修改玩家生死状态；所有夜间动作统一汇总为 `NightActionSet` 后交给 `NightResolver` 结算。

```python
class NightActionSet:
    round: int
    guard_target: int | None
    wolf_kill_target: int | None
    witch_save_target: int | None
    witch_poison_target: int | None
    seer_check_target: int | None
```

结算规则：

1. 守卫守护目标先记录为保护状态，不立即产生公开结果。
2. 狼人击杀目标记录为 `wolf_kill_target`。
3. 女巫在规则允许时可获知当晚狼刀目标，并选择是否使用解药；毒药目标独立记录。
4. 预言家查验结果只写入预言家私有记忆，不进入公开日志。
5. 结算器根据规则同时计算狼刀、守护、解药、毒药的最终死亡列表。
6. 猎人等死亡触发技能不在夜间结算器中直接执行，而是在死亡确认后进入 `ON_DEATH_SKILL` 状态。

默认结算口径：

| 场景 | 默认结果 | 可配置项 |
| ---- | -------- | -------- |
| 狼刀目标被守卫守护 | 不死亡 | `guard_blocks_wolf_kill` |
| 狼刀目标被女巫解救 | 不死亡 | `witch_save_blocks_wolf_kill` |
| 守卫和女巫同救同一狼刀目标 | 死亡 | `guard_witch_same_target_dies` |
| 同一玩家同时被狼刀和毒药命中 | 死亡，死亡原因记录为多原因 | `merge_death_causes` |
| 女巫毒杀猎人 | 是否可开枪由规则决定 | `hunter_can_shoot_on_witch_kill` |
| 守卫连续两晚守同一人 | 默认不允许，非法动作触发重试或降级 | `guard_cannot_guard_same_twice` |

夜间结算产出 `NightResolutionResult`，包含：

- `deaths`: 最终死亡玩家列表
- `death_causes`: 仅系统和上帝视角可见的死因
- `private_results`: 预言家查验、女巫用药等只对指定 Agent 可见的结果
- `public_announcement`: 天亮后对所有存活玩家公开的死亡公告

### 2. 游戏状态机 (`core/state.py`)

游戏状态机的完整状态转换图：

```
WAITING ──(start, enable_sheriff)──→ SHERIFF_ELECTION ──(elected)──→ NIGHT_BEGIN
   │                                                                      ▲
   └────(start, no sheriff)───────────────────────────────────────────────┘

NIGHT_BEGIN → WOLF_DISCUSS → NIGHT_ACTIONS → NIGHT_RESOLVE → DAWN
                                                     │
                                                     ▼
ANNOUNCE_DEATHS → LAST_WORDS(skip/done) → WIN_CHECK ──(no winner after night)──→ DISCUSS_ORDER
                                                 │                                      │
                                                 │                                      ▼
                                                 │                                    DISCUSS
                                                 │                                      │
                                                 │                                      ▼
                                                 │                                     VOTE
                                                 │                                      │
                                                 │                                      ▼
                                                 │                                  VOTE_RESULT
                                                 │                                      │
                                                 │                                      ▼
                                                 │                                    EXECUTE
                                                 │                                      │
                                                 │                                      ▼
                                                 │                         LAST_WORDS(skip/done)
                                                 │                                      │
                                                 │                                      ▼
                                                 │                         ON_DEATH_SKILL(skip/done)
                                                 │                                      │
                                                 └──────(has winner)──→ GAME_END        ▼
                                                                                  WIN_CHECK

WIN_CHECK ──(no winner after day)──→ NIGHT_BEGIN
WIN_CHECK ──(has winner)──→ GAME_END

任意运行中状态 ──(pause)──→ PAUSED ──(resume)──→ 原状态
任意LLM动作状态 ──(parse/timeout/validation failed)──→ RETRY_OR_FALLBACK ──→ 原状态
任意运行中状态 ──(manual stop/fatal error)──→ ABORTED
```

状态说明：

| 状态                 | 说明                           |
| -------------------- | ------------------------------ |
| `WAITING`          | 等待玩家加入，配置对局         |
| `SHERIFF_ELECTION` | 警长竞选阶段（可选）           |
| `NIGHT_BEGIN`      | 夜晚开始，切换视觉模式         |
| `WOLF_DISCUSS`     | 狼人内部协商击杀目标           |
| `NIGHT_ACTIONS`    | 各角色按优先级执行夜间技能     |
| `NIGHT_RESOLVE`    | 统一结算夜间行动，生成死亡与私有结果 |
| `DAWN`             | 天亮，结算昨夜结果             |
| `ANNOUNCE_DEATHS`  | 公布昨夜死亡信息               |
| `LAST_WORDS`       | 出局玩家发表遗言               |
| `ON_DEATH_SKILL`   | 死亡触发技能执行（猎人开枪等） |
| `DISCUSS_ORDER`    | 确定白天发言起点和发言顺序     |
| `DISCUSS`          | 白天自由讨论                   |
| `VOTE`             | 投票环节                       |
| `VOTE_RESULT`      | 计算投票结果，处理平票/重投/无人出局 |
| `EXECUTE`          | 执行投票结果                   |
| `WIN_CHECK`        | 检查胜负条件                   |
| `GAME_END`         | 游戏结束                       |
| `PAUSED`           | 对局暂停，保留当前状态         |
| `RETRY_OR_FALLBACK`| LLM 输出失败后的重试或降级决策 |
| `ABORTED`          | 手动终止或不可恢复错误         |

可选路径与异常路径：

- 未启用警长时，开始游戏后直接进入 `NIGHT_BEGIN`。
- 投票平票时按规则进入重投、无人出局或随机处决；重投仍平票时使用规则配置的最终处理方式。
- 处决、夜间死亡、猎人开枪等每次造成出局后都进入 `WIN_CHECK`；夜间后的无胜负流向白天讨论，白天后的无胜负流向下一夜。
- LLM 超时、解析失败或动作非法时进入 `RETRY_OR_FALLBACK`，超过重试上限后使用规则配置的降级动作。
- `PAUSED` 可从任意运行中状态进入，恢复时回到暂停前状态。

### 3. Agent 系统 (`agents/base.py`)

每个AI玩家是一个 Agent，核心结构：

```
Agent
├── model_config    # LLM模型配置（provider, model_name, base_url, api_key）
├── personality     # 人格特质（影响prompt风格）
├── role            # 当前角色（游戏开始后分配）
├── thinking_mode   # 是否开启思维链
├── is_alive        # 是否存活
├── memory          # 游戏内记忆（公共+私有）
│   ├── public      # 公共记忆：所有玩家可见
│   └── private      # 私有记忆：仅自己可见
└── conversation    # 与LLM的对话历史
```

**记忆隔离**是关键设计：每个Agent只能看到自己"应该"知道的信息。例如：

- 狼人知道同伴是谁，但不知道预言家查了谁
- 预言家知道自己的查验结果，但不知道狼人杀了谁

**记忆分类**：

| 级别     | 可见范围 | 示例 |
| -------- | -------- | ---- |
| 公共记忆 | 所有玩家 | 白天发言、投票结果、死亡公告、警长竞选结果 |
| 私有记忆 | 仅自己 | 自己的角色身份、预言家查验结果、女巫用药状态、个人策略、thinking |

狼人同伴信息和夜间协商上下文不作为独立的阵营共享记忆持久化。引擎在 `WOLF_DISCUSS` 阶段临时向存活狼人注入本轮协商上下文，阶段结束后协商内容写入夜晚日志；后续狼人是否能回忆历史协商，由引擎从夜晚日志中按狼人身份过滤后注入私有上下文。

**thinking 可见性**：

- `thinking` 只对产生该内容的模型自身和人类观赛者可见。
- `thinking` 不进入公开发言，不参与投票讨论文本，也不会被其他 Agent 当作公共信息读取。
- 日志中 `thinking` 事件标记为 `visibility: ["observer", "player:{self}"]`。

记忆压缩（可选）：当游戏轮次较多、对话历史超出模型上下文窗口时，可启用摘要压缩策略——将早期轮次的详细对话压缩为自然语言摘要，保留关键决策节点，具体策略可在规则配置中开关。

### 4. Prompt 工程 (`agents/prompts.py`)

Prompt 采用**分层组装**设计：

```
System Prompt:
  ┌─────────────────────────┐
  │   [规则层]              │  ← 游戏规则
  │   [身份层]              │  ← 你的角色和技能
  │   [人格层]              │  ← 你的性格描述
  │   [记忆层]              │  ← 你已知的信息
  │   [约束层]              │  ← 信息隔离约束（不得泄露角色特权信息）
  └─────────────────────────┘

User Prompt:
  [当前阶段指令 + 要求输出格式]

思考模式 ON 时额外要求:
  "请先进行内部推理（thinking字段），再给出公开行为（action/speech字段）"
```

要求模型返回结构化 JSON：

```json
{
  "thinking": "我是狼人，预言家刚说查了3号，我应该...",
  "action": {"target": 3, "type": "vote"},
  "speech": "我觉得3号很可疑..."
}
```

### 5. 角色系统 (`roles/base.py`)

```python
class BaseRole:
    name: str                    # 角色名
    faction: Faction             # 阵营：WOLF / VILLAGE / OTHER
    night_priority: int          # 夜间行动优先级（数值小优先）
    skills: list[Skill]          # 技能列表
  
    def night_action(self, agent, state) -> ActionResult
    def day_action(self, agent, state) -> ActionResult
    def on_death(self, agent, state) -> ActionResult | None  # 死亡触发技能
    def get_night_prompt(self, state) -> str
    def get_day_prompt(self, state) -> str
```

角色通过继承 `BaseRole` 扩展，新增角色只需实现对应接口，无需改动引擎。其中 `on_death` 用于处理死亡触发型技能（如猎人开枪）。

### 6. LLM 调用层 (`llm/`)

#### 6.1 多格式适配器 (`llm/adapter.py`)

采用适配器模式统一不同 LLM 提供商的接口：

```python
class ProviderAdapter(ABC):
    @abstractmethod
    async def complete(self, messages, **kwargs) -> LLMResponse
  
    @abstractmethod
    def parse_response(self, raw_response) -> dict
```

内置适配器：

| 适配器            | 适配格式                    | 支持模型                                  |
| ----------------- | --------------------------- | ----------------------------------------- |
| `OpenAIAdapter` | OpenAI Chat Completions API | GPT-4、GPT-3.5、DeepSeek、Qwen 等兼容接口 |
| `ClaudeAdapter` | Anthropic Messages API      | Claude 3.5/3/系列                         |

适配器选择通过配置文件 `configs/models/providers.yaml` 指定，运行时自动加载。

> **注意**：`TokenPlanAdapter` 已暂时移除，待 Token Plan 格式稳定后再考虑接入。

#### 6.2 输出解析与校验 (`agents/parser.py`)

模型返回的 JSON 需要经过解析与校验：

```python
class OutputParser:
    def parse(self, raw: str) -> ParsedOutput:
        """将模型原始输出解析为结构化数据"""
        # 1. 提取JSON（兼容markdown代码块包裹的情况）
        # 2. 解析为dict
  
    def validate(self, output: ParsedOutput, context: GameContext) -> ValidatedOutput:
        """校验动作合法性"""
        # - action.target 是否为合法玩家编号
        # - action.type 是否为当前阶段允许的动作
        # - 技能使用是否符合冷却/限制规则
        # 非法时抛出 ValidationError，触发重试
```

#### 6.3 重试与降级策略 (`llm/retry.py`)

```python
class RetryPolicy:
    max_retries: int = 3                    # 最大重试次数
    retry_on_parse_error: bool = True        # 解析失败时重试
    retry_on_validation_error: bool = True   # 校验失败时重试
    retry_on_timeout: bool = True            # 超时时重试
    retry_on_rate_limit: bool = True         # 限流时重试（自动退避）
    fallback_model: str | None = None        # 降级备选模型
```

重试流程：

```
LLM调用 → 解析 → 校验
  │         │       │
  │(失败)   │(失败)  │(不合法)
  │         │       │
  └──── 重试(带原始错误提示) ────┘
                 │
          超过最大重试次数？
           ├─ 是 → 降级到备选模型 或 随机决策
           └─ 否 → 返回成功结果
```

#### 6.4 并发控制

白天正式发言不能并行。发言顺序由 `DISCUSS_ORDER` 阶段确定：

- 如果存在存活警长，警长先选择起始发言玩家。
- 如果没有存活警长或未启用警长机制，引擎随机选择一名存活玩家作为起始发言玩家。
- 从起始玩家开始按玩家编号递增顺序依次发言，到最大编号后回到最小编号，跳过已出局玩家。
- 每位玩家发言时能看到此前已经公开的白天发言、投票和死亡公告；不能看到尚未轮到的玩家即将生成的发言。

LLM 调用仍需要并发管理，但只用于不同对局、夜间互不依赖动作、裁判评选或批量模拟等场景：

- 每个 provider 维护独立的信号量，控制并发请求数
- 同一 provider 的请求排队执行，不同 provider 可并行
- 支持按 provider 配置速率限制（`rpm`/`tpm`）

### 7. 规则系统 (`configs/rules/classic.yaml`)

规则可YAML配置，模型在游戏开始时读取规则：

```yaml
name: "经典狼人杀"
version: "1.0"
phases:
  night_order: [guard, werewolf, witch, seer]
  day_order: [announce, discuss, vote, execute]
  enable_sheriff: true                    # 是否启用警长
  enable_last_words: true                 # 是否启用遗言
  enable_wolf_discuss: true               # 狼人是否可以夜间讨论
  day_speech_order: sheriff_choose_or_random_clockwise
voting:
  type: majority        # majority / plurality
  tie_handling: revote   # revote / no_elimination / random
  allow_abstain: true
  sheriff_vote_weight: 1.5               # 警长票权重
win_conditions:
  wolves_eliminated: "好人阵营胜利"
  wolves_equal_villagers: "狼人阵营胜利"
roles:
  werewolf: {min: 2, max: 4}
  seer: {min: 1, max: 1}
  witch: {min: 1, max: 1}
  hunter: {min: 0, max: 1}
  guard: {min: 0, max: 1}
  villager: {min: 0, max: 99}
special_rules:
  witch_can_self_save: false             # 女巫首夜能否自救
  hunter_can_shoot_on_witch_kill: true   # 猎人被女巫毒死能否开枪
  guard_cannot_guard_same_twice: true    # 守卫能否连续守同一人
  guard_blocks_wolf_kill: true
  witch_save_blocks_wolf_kill: true
  guard_witch_same_target_dies: true      # 守卫和女巫同救同一人时是否死亡
  merge_death_causes: true                # 多死因是否合并记录
  first_night_has_last_words: true        # 首夜死亡是否有遗言
  sheriff_can_transfer: true              # 警长能否移交警徽
logs:
  split_day_night: true
  night_log_visibility: observer_only
  event_sourcing: true
memory_compression:
  enabled: false                          # 是否启用记忆压缩
  threshold_rounds: 5                      # 超过N轮后启用压缩
  strategy: summarize                      # summarize / sliding_window
```

### 8. 数据流与实时通信

```
 用户操作                后端处理                  前端展示
┌──────┐  HTTP/WS  ┌──────────┐           ┌──────────┐
│Setup │──────────→│创建对局   │           │          │
│Page  │           │分配角色   │──WS──────→│ Game     │
│      │           │          │           │ Board    │
└──────┘           │引擎循环   │           │          │
                   │  ↓       │           │ ChatPanel│
                   │LLM调用   │──WS──────→│ VotePanel│
                   │  ↓       │           │Thinking  │
                   │状态更新   │           │ Viewer   │
                   │  ↓       │           │          │
                   │事件广播   │──WS──────→│          │
                   │  ↓       │           └──────────┘
                   │日志持久化 │
                   └──────────┘
```

### 9. 日志系统 (`storage/game_log.py`)

日志采用事件溯源设计：状态变化不只保存最终快照，而是保存每一步事件，方便回放、断点恢复、调试 LLM 输出和后续统计。每局游戏生成一个 JSON 日志文件，内部按可见性拆分为白天日志、夜晚日志和观赛者日志。

- **白天日志 `day_log`**：保存所有公开信息，包括发言、投票、处决、遗言、死亡公告、警长竞选等；所有 Agent 和人类观赛者可见。
- **夜晚日志 `night_log`**：保存夜间行动、夜间协商、技能目标、真实死因等；仅上帝视角/人类观赛者可见，不直接暴露给非授权 Agent。
- **观赛者日志 `observer_log`**：保存 thinking、模型原始输出、裁判评语等只面向观赛与分析的信息。
- **私有结果 `private_events`**：保存预言家查验结果、女巫用药状态等，仅在构造对应 Agent 上下文时注入。

基础事件结构：

```json
{
  "event_id": 42,
  "schema_version": "1.0",
  "game_id": "uuid",
  "round": 2,
  "phase": "day_2_discuss",
  "event_type": "speech",
  "player_id": 3,
  "visibility": ["public"],
  "causation_id": 41,
  "data": {
    "content": "我怀疑4号是狼人..."
  },
  "raw_model_output": {
    "thinking": "...",
    "speech": "我怀疑4号是狼人..."
  },
  "validated_action": {
    "type": "speech"
  },
  "state_hash": "sha256:...",
  "timestamp": "..."
}
```

完整日志结构示例：

```json
{
  "schema_version": "1.0",
  "game_id": "uuid",
  "config": { "players": [...], "rules": "classic", ... },
  "day_log": [
    {
      "event_id": 10,
      "phase": "day_1_discuss",
      "event_type": "speech",
      "player_id": 2,
      "visibility": ["public"],
      "data": {"content": "我怀疑4号是狼人..."},
      "timestamp": "..."
    },
    {
      "event_id": 18,
      "phase": "day_1_vote",
      "event_type": "vote",
      "player_id": 2,
      "visibility": ["public"],
      "data": {"target": 4},
      "timestamp": "..."
    }
  ],
  "night_log": [
    {
      "event_id": 3,
      "phase": "night_1",
      "event_type": "night_action",
      "role": "werewolf",
      "player_id": 1,
      "visibility": ["observer"],
      "action": {"type": "kill", "target": 3},
      "timestamp": "..."
    }
  ],
  "observer_log": [
    {
      "event_id": 11,
      "phase": "day_1_discuss",
      "event_type": "thinking",
      "player_id": 2,
      "visibility": ["observer", "player:2"],
      "data": {"thinking": "实际上我是预言家，我查了4号..."},
      "timestamp": "..."
    }
  ],
  "result": { "winner": "village", "rounds": 5 },
  "mvp": {
    "player_id": 3,
    "role": "werewolf",
    "model": "gpt-4o",
    "reason": "该玩家成功伪装成预言家，连续两晚引导好人阵营误投村民..."
  }
}
```

### 10. 裁判 AI 与 MVP 评选 (`agents/judge.py`)

每局游戏配置一名**裁判 AI**，在游戏结束后自动执行 MVP 评选：

```
GAME_END → 裁判 AI 读取完整日志 → 在胜利阵营中评选 MVP → 输出理由
```

**裁判 AI 配置**：

- 在 Setup 阶段与玩家模型一同配置（选择模型、provider、人格提示词）
- 裁判 AI 不参与游戏，仅在游戏结束时被调用
- 支持为裁判 AI 配置不同的"评判风格"（如严格型、鼓励型、逻辑分析型）

**评选流程**：

1. 游戏结束后，引擎将本局完整日志（含所有公开发言、投票、思维过程、角色身份）打包发送给裁判 AI
2. 裁判 AI 只能在**胜利阵营**的存活玩家中评选 MVP
3. 裁判 AI 返回结构化结果：
   ```json
   {
     "mvp_player_id": 3,
     "reason": "..."
   }
   ```
4. 结果写入对局日志，并通过 WebSocket 推送到前端展示

**评选维度参考**（由裁判 AI 的 prompt 引导，不做硬编码限制）：

- 作为狼人时的伪装与欺骗效果
- 作为好人时的推理与带票能力
- 关键轮次的决策质量
- 对团队胜利的贡献度

## 游戏规则

### 核心规则

#### 角色阵营

| 阵营     | 角色   | 说明                                                                               |
| -------- | ------ | ---------------------------------------------------------------------------------- |
| 狼人阵营 | 狼人   | 夜间选择一名玩家击杀，互相知道身份                                                 |
| 好人阵营 | 村民   | 无特殊技能，依靠推理发言辨别狼人                                                   |
| 好人阵营 | 预言家 | 每晚可查验一名玩家的身份（是否为狼人）                                             |
| 好人阵营 | 女巫   | 拥有一瓶解药（救人）和一瓶毒药（毒人），各限用一次                                 |
| 好人阵营 | 猎人   | 死亡时（被投票处决或被狼人杀死）可开枪带走一名玩家                                 |
| 好人阵营 | 守卫   | 每晚可选择守护一名玩家，被守护的玩家若被狼人袭击则不会死亡；不可连续两晚守护同一人 |

#### 游戏流程

1. **角色分配**：随机或手动分配角色
2. **警长竞选**（如启用）：玩家依次发表竞选宣言，投票选出警长
3. **夜晚阶段**：
   - 守卫选择守护对象
   - 狼人协商选择击杀目标
   - 女巫决定是否使用解药/毒药
   - 预言家选择查验对象
4. **天亮公布**：公布昨夜死亡信息（不公布死因和角色）
5. **遗言环节**（如启用）：出局玩家发表遗言
6. **白天讨论**：由警长指定起始发言玩家，然后从该玩家开始按编号递增顺序依次发言；如果没有警长，则随机选择一名存活玩家作为起点
7. **投票处决**：投票选出一名嫌疑人，票数最高者被处决（警长票算1.5票）
8. **处决后遗言**（如启用）：被处决者发表遗言
9. **死亡触发技能**：被处决者若是猎人，可选择开枪
10. **胜负判定**：检查是否满足胜利条件
11. 若未分出胜负，回到步骤3

#### 胜利条件

- **好人阵营胜利**：所有狼人被淘汰
- **狼人阵营胜利**：存活狼人数量 ≥ 存活好人数量

#### 胜负判定方案

胜负判定由 `WIN_CHECK` 阶段统一执行。Prompt 可以向 Agent 解释胜负目标，但最终是否结束游戏必须由状态机根据真实角色和存活状态判断。

判定触发时机：

- 夜间 `NIGHT_RESOLVE` 完成并确认死亡后
- 白天 `EXECUTE` 完成处决后
- `ON_DEATH_SKILL` 完成并确认额外死亡后
- 手动终止或不可恢复错误进入 `ABORTED` 时，不判定正常胜负

默认判定顺序：

1. 统计存活狼人数量 `alive_wolves`。
2. 统计存活好人数量 `alive_villagers`，包括村民和所有神职。
3. 如果 `alive_wolves == 0`，好人阵营胜利。
4. 如果 `alive_wolves >= alive_villagers`，狼人阵营胜利。
5. 否则游戏继续进入下一阶段。

可扩展判定：

- 如果后续引入屠边规则，可改为 `wolves_kill_all_villagers` 或 `wolves_kill_all_gods`。
- 如果引入第三方角色，`WinConditionEvaluator` 按优先级先判断第三方特殊胜利，再判断狼人/好人阵营。
- 若同一次结算中好人和狼人条件同时满足，按规则配置 `win_tie_breaker` 决定优先级。

#### 警长机制

- 警长通过竞选产生，票数最高者当选
- 警长投票时票数算1.5票
- 警长死亡时可移交警徽给任意存活玩家
- 若警长被淘汰且未移交警徽，警长职位本轮作废

#### 遗言环节

- 被狼人杀害的玩家：如启用遗言规则，可在公布死亡后发表遗言
- 被投票处决的玩家：可在处决前发表遗言
- 遗言内容对所有存活玩家公开

#### 首夜特殊规则

- 女巫首夜是否可以自救：由规则配置决定（默认不可）
- 首夜死亡是否享有遗言：由规则配置决定
- 守卫首夜是否可以空守：允许

#### 死亡触发技能

部分角色在死亡时触发特殊技能，需要单独处理：

| 角色 | 触发条件                | 技能效果                   |
| ---- | ----------------------- | -------------------------- |
| 猎人 | 被投票处决 / 被狼人杀死 | 可选择开枪带走一名存活玩家 |
| 猎人 | 被女巫毒杀              | 由规则配置决定是否可以开枪 |

#### 狼人内部协商

- 夜间阶段，所有狼人互通信息，协商选择击杀目标
- 协商为独立阶段（`WOLF_DISCUSS`），采用固定轮次的结构化协商流程：
  1. **第一轮表决**：每位狼人必须给出一个击杀目标
  2. **计票规则**：得票数最多的目标直接确认为当晚击杀目标
  3. **平票处理**：若出现平票，平票目标相关的狼人各简短说明理由，随后进行第二轮表决，依旧按多数票选择
  4. **仍未达成**：若第二轮仍平票，从讨论中出现过的目标中随机指定一位作为击杀目标
- 协商内容在夜间阶段仅对狼人可见；阶段结束后写入夜晚日志，夜晚日志仅上帝视角可见，不进入公共白天日志

### 规则可配置项

所有规则均可在 YAML 配置中自定义，包括但不限于：

- 角色数量范围
- 警长机制开关与参数
- 遗言规则开关与参数
- 首夜特殊规则
- 投票规则（多数决/相对多数/平票处理）
- 胜利条件
- 记忆压缩策略

## API 设计

### REST API

| 方法 | 路径                                          | 说明                                |
| ---- | --------------------------------------------- | ----------------------------------- |
| POST | `/api/games`                                | 创建新对局                          |
| GET  | `/api/games/{game_id}`                      | 获取对局状态                        |
| POST | `/api/games/{game_id}/start`                | 开始游戏                            |
| POST | `/api/games/{game_id}/pause`                | 暂停对局                            |
| POST | `/api/games/{game_id}/resume`               | 恢复对局                            |
| POST | `/api/games/{game_id}/step`                 | 单步推进一个状态或一个动作          |
| POST | `/api/games/{game_id}/stop`                 | 手动终止对局，进入 `ABORTED`        |
| POST | `/api/games/{game_id}/rerun-action`         | 重新执行最近一次失败或指定动作      |
| POST | `/api/games/{game_id}/action`               | 提交玩家操作（供降级随机决策使用）  |
| GET  | `/api/games/{game_id}/mvp`                  | 获取本局 MVP 评选结果（游戏结束后） |
| GET  | `/api/games/{game_id}/log`                  | 获取对局完整日志                    |
| GET  | `/api/games/{game_id}/log/day`              | 获取白天公开日志                    |
| GET  | `/api/games/{game_id}/log/night`            | 获取夜晚上帝视角日志                |
| GET  | `/api/games/{game_id}/events?after_id=0`    | 按事件 ID 增量获取事件，用于重连恢复 |
| GET  | `/api/games/{game_id}/thinking/{player_id}` | 获取指定玩家的思维过程              |
| GET  | `/api/games`                                | 列出所有对局                        |
| POST | `/api/configs/validate`                     | 校验规则、角色、模型配置是否可运行  |
| GET  | `/api/configs/roles`                        | 获取角色配置列表                    |
| GET  | `/api/configs/rules`                        | 获取规则配置列表                    |
| GET  | `/api/configs/models`                       | 获取可用模型列表                    |

### WebSocket 事件协议

事件类型枚举与数据格式：

客户端连接时可携带 `last_event_id`，例如 `/api/ws/games/{game_id}?last_event_id=42`。服务端先补发 `event_id > 42` 的事件，再推送实时事件，保证页面刷新或网络断开后可以恢复。

```typescript
enum GameEventType {
  // 游戏生命周期
  GAME_START          = "game_start",
  GAME_END            = "game_end",
  GAME_PAUSED         = "game_paused",
  GAME_RESUMED        = "game_resumed",
  GAME_ABORTED        = "game_aborted",

  // 阶段转换
  PHASE_CHANGE        = "phase_change",      // 阶段切换
  STATE_SNAPSHOT      = "state_snapshot",    // 重连后的状态快照
  
  // 警长竞选
  SHERIFF_ELECTION    = "sheriff_election",   // 警长竞选开始
  SHERIFF_RESULT      = "sheriff_result",     // 警长选举结果

  // 夜间阶段
  NIGHT_BEGIN         = "night_begin",
  WOLF_DISCUSS        = "wolf_discuss",       // 狼人协商
  NIGHT_ACTION        = "night_action",       // 角色夜间行动

  // 白天阶段
  DAWN                = "dawn",               // 天亮
  DEATH_ANNOUNCEMENT  = "death_announcement",  // 死亡公告

  // 讨论与投票
  SPEECH              = "speech",              // 发言
  LAST_WORDS          = "last_words",          // 遗言
  VOTE                = "vote",                // 投票
  VOTE_RESULT         = "vote_result",         // 投票结果
  EXECUTE             = "execute",             // 处决

  // 死亡触发
  ON_DEATH_SKILL      = "on_death_skill",      // 死亡触发技能

  // 思维过程
  THINKING            = "thinking",            // Agent 思维过程（按需推送）

  // 运行控制与错误
  ACTION_RETRY        = "action_retry",
  ACTION_FALLBACK     = "action_fallback",
  ERROR               = "error",
}
```

每个事件的数据结构：

```json
{
  "event_type": "speech",
  "event_id": 42,
  "game_id": "uuid",
  "round": 1,
  "phase": "day_1",
  "player_id": 3,
  "data": {
    "content": "我怀疑4号是狼人..."
  },
  "timestamp": "2025-05-02T12:00:00Z"
}
```

### 环境变量与密钥管理

通过 `.env` 文件管理敏感配置，`.env.example` 提供模板：

```bash
# Application
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false

# OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_BASE_URL=https://api.anthropic.com

# Custom Providers (OpenAI-compatible)
CUSTOM_PROVIDER_1_API_KEY=xxx
CUSTOM_PROVIDER_1_BASE_URL=https://xxx/v1
CUSTOM_PROVIDER_1_MODEL=xxx

# Log Storage
LOG_DIR=./logs
```

`.env` 文件已添加到 `.gitignore`，确保密钥不会被提交到仓库。

## 前端设计

### 设计理念

用户以**上帝视角**观看整场游戏，可以看到所有信息：

- 每个模型的公开发言和投票行为
- 每个模型的思维过程和推理逻辑（thinking）
- 所有角色的身份和技能使用情况
- 夜间行动的详细信息

### 页面布局

```
┌────────────────────────────────────────────────────────────┐
│  LyingLLM  ·  第 3 轮  ·  白天讨论阶段          [⚙️][📋][🔄] │
├──────────────┬──────────────────────────────┬───────────────┤
│  玩家 1      │                              │  玩家 7       │
│  🐺 狼人     │                              │  🔮 预言家    │
│  ████████    │     中 间 信 息 展 示 区       │  ████████    │
│  [思维过程]  │                              │  [思维过程]    │
│              │  ┌────────────────────────┐  │               │
│  玩家 2      │  │  📢 玩家3: "我觉得4号   │  │  玩家 8       │
│  🏠 村民     │  │     很可疑..."          │  │  🏠 村民      │
│  ████████    │  │                        │  │  ████████    │
│  [思维过程]  │  │  💭 玩家3 思考:         │  │  [思维过程]    │
│              │  │  "我是预言家，查了4号    │  │               │
│  ...         │  │   确实是狼人..."         │  │  ...         │
│              │  │                        │  │               │
│  玩家 6      │  │  🗳️ 投票: 玩家3 → 玩家4 │  │  玩家 12      │
│  🧙 女巫     │  └────────────────────────┘  │  🛡️ 守卫     │
│  ████████    │                              │  ████████    │
│  [思维过程]  │                              │  [思维过程]    │
├──────────────┴──────────────────────────────┴───────────────┤
│  日志时间线:  [夜1: 🔴] → [白天1: 投票] → [夜2: ⏳]        │
└────────────────────────────────────────────────────────────┘
```

### 日夜视觉模式

- **日间模式**：明亮背景，暖色调，显示白天讨论和投票界面
- **夜间模式**：深色背景，冷色调，显示夜间行动（上帝视角可见所有角色行动，但标记"仅XX可见"

日夜切换随游戏阶段自动切换，用户也可手动锁定某一模式。

### 三大页面

| 页面              | 功能                                                                   |
| ----------------- | ---------------------------------------------------------------------- |
| **Setup**   | 配置玩家数量、模型选择、性格设定、角色分配、规则选择，以及裁判 AI 模型 |
| **Game**    | 实时观战，上帝视角查看所有信息，可切换查看各玩家思维过程               |
| **History** | 浏览历史对局，查看日志和回放                                           |

## 关键设计决策

1. **信息隔离**：Agent 只维护公共记忆和私有记忆，不设置阵营共享记忆；引擎按阶段和身份临时注入必要上下文
2. **异步串行执行**：夜间行动按优先级收集并统一结算；白天发言按警长指定或随机起点依次串行
3. **思考模式可视化**：`thinking` 字段与 `speech` 分离存储，仅模型自身和人类观赛者可见，不算作公开发言
4. **规则即Prompt**：规则文件直接转化为 Agent system prompt 的一部分，确保所有模型"读懂"规则；胜负结束由 `WIN_CHECK` 按真实状态统一判定
5. **角色可扩展**：新角色只需继承 `BaseRole` + 添加 YAML 配置，无需改动引擎
6. **死亡触发技能**：通过 `on_death` 回调接口统一处理，不破坏主循环逻辑
7. **多格式LLM适配**：适配器模式统一不同提供方的接口，新增仅需实现 `ProviderAdapter`
8. **输出校验与重试**：所有模型输出经过解析→校验→重试的管道，确保游戏流程不被无效输出中断
9. **上帝视角**：前端默认显示所有信息，用户可以自由查看任意玩家的思维过程

## 后续可扩展方向

- **批量对局与统计**：支持批量运行多局游戏，自动生成模型胜率、存活率等统计报告
- **裁判 AI 扩展**：支持多裁判投票制、按维度打分（欺骗/推理/领导/贡献）
- **多人类型支持**：加入"上帝"人类玩家主持游戏（可选）
- **回放系统**：基于日志文件完整回放游戏过程
- **模型对比面板**：多局统计，横向对比不同模型表现
- **记忆压缩策略**：支持多种压缩方式（摘要、滑动窗口、重要度排序），可按模型上下文窗口大小自动选择
