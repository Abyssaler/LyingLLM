import sys
sys.path.insert(0, '.')

import asyncio
from app.roles.base import BaseRole, ActionResult, GameContext
from app.roles.werewolf import Werewolf
from app.roles.villager import Villager
from app.roles.seer import Seer
from app.roles.witch import Witch
from app.roles.hunter import Hunter
from app.roles.guard import Guard
from app.roles import ROLE_REGISTRY, create_role
from app.models.role import Faction

# Test role registry
assert len(ROLE_REGISTRY) == 6, f"Expected 6 roles, got {len(ROLE_REGISTRY)}"
print(f"1. ROLE_REGISTRY has {len(ROLE_REGISTRY)} roles: OK")

for key in ["werewolf", "villager", "seer", "witch", "hunter", "guard"]:
    role = create_role(key)
    assert isinstance(role, BaseRole), f"{key} is not BaseRole"
print("2. create_role for all keys: OK")

w = create_role("werewolf")
assert w.name == "狼人"
assert w.faction == Faction.WOLF
assert w.night_priority == 2
assert w.has_night_action()
assert not w.has_on_death_skill()
print("3. Werewolf role: OK")

v = create_role("villager")
assert v.name == "村民"
assert v.faction == Faction.VILLAGE
assert not v.has_night_action()
print("4. Villager role: OK")

s = create_role("seer")
assert s.faction == Faction.VILLAGE
assert s.has_night_action()
print("5. Seer role: OK")

wi = create_role("witch")
assert wi.has_night_action()
assert wi.has_save_potion
assert wi.has_poison_potion
print("6. Witch role: OK")

h = create_role("hunter")
assert h.has_on_death_skill()
assert not h.has_night_action()
print("7. Hunter role: OK")

g = create_role("guard")
assert g.has_night_action()
assert g.last_guard_target is None
print("8. Guard role: OK")

ctx = GameContext(round=1, phase="NIGHT_ACTIONS", alive_player_ids=[1,2,3,4,5,6,7,8,9])
assert ctx.round == 1
print("9. GameContext: OK")

# Guard same-target block
g.last_guard_target = 1
ctx2 = GameContext(round=2, alive_player_ids=[1,2,3], extra={"guard_target": 1})
result = asyncio.get_event_loop().run_until_complete(g.night_action(None, ctx2))
assert not result.success
print("10. Guard same-target block: OK")

ctx3 = GameContext(round=2, alive_player_ids=[1,2,3], extra={"guard_target": 2})
result2 = asyncio.get_event_loop().run_until_complete(g.night_action(None, ctx3))
assert result2.success
print("11. Guard different target: OK")

# ── Memory ──
from app.memory.game_memory import GameMemory, MemoryVisibility
mem = GameMemory()
mem.set_round(1)
mem.add_public("night_1", "death", "玩家3号昨晚死亡")
mem.add_private("night_1", "seer_check", "你查验了玩家5号，结果为好人")
mem.add_faction("night_1", "wolf_discuss", "狼人协商击杀玩家3号")

assert len(mem.get_public()) == 1
assert len(mem.get_private()) == 1
assert len(mem.get_faction()) == 1
print("12. GameMemory add/get: OK")

wolf_view = mem.get_visible_for(include_faction=True)
assert len(wolf_view) == 3
villager_view = mem.get_visible_for(include_faction=False)
assert len(villager_view) == 2
print("13. Memory visibility isolation: OK")

ctx_text = mem.get_context_for_agent(include_faction=True)
assert "第1轮" in ctx_text
print("14. Memory context text: OK")

data = mem.to_dict()
mem2 = GameMemory.from_dict(data)
assert len(mem2.get_public()) == 1
assert len(mem2.get_faction()) == 1
print("15. Memory serialization: OK")

# ── Personality ──
from app.agents.personality import Personality, PersonalityTrait
p = Personality(name="狡猾策略家", description="善于伪装和推理", traits=[PersonalityTrait.DECEPTIVE, PersonalityTrait.STRATEGIC])
text = p.to_prompt_text()
assert "狡猾策略家" in text
assert "deceptive" in text
print("16. Personality: OK")

# ── Conversation ──
from app.llm.message import ConversationManager
cm = ConversationManager()
cm.add_system("你是一个狼人杀玩家")
cm.add_user("当前是白天讨论阶段")
cm.add_assistant("我觉得3号很可疑")
assert cm.message_count == 3
assert cm.has_system
cm.clear_conversation()
assert cm.message_count == 1
print("17. ConversationManager: OK")

cm.add_user("test")
cm.add_user("test2")
msgs_window = cm.get_context_window(max_tokens=300, tokens_per_msg=100)
assert len(msgs_window) >= 1
print("18. ConversationManager context window: OK")

# ── Parser ──
from app.agents.parser import OutputParser, ActionValidator, ParsedOutput, ParseError, ValidationError

parser = OutputParser()
raw = '```json\n{"thinking": "我怀疑3号", "action": {"target": 3, "type": "vote"}, "speech": "3号很可疑"}\n```'
parsed = parser.parse(raw)
assert parsed.thinking == "我怀疑3号"
assert parsed.action["target"] == 3
assert parsed.speech == "3号很可疑"
print("19. Parser markdown JSON: OK")

raw2 = '{"thinking": "test", "action": {"target": 5, "type": "check"}}'
parsed2 = parser.parse(raw2)
assert parsed2.thinking == "test"
assert parsed2.action["target"] == 5
print("20. Parser plain JSON: OK")

validator = ActionValidator()
validated = validator.validate(parsed, alive_player_ids=[1,2,3,4,5,9])
assert validated.action["target"] == 3
print("21. ActionValidator: OK")

try:
    bad_parsed = ParsedOutput(action={"target": 99, "type": "vote"})
    validator.validate(bad_parsed, alive_player_ids=[1,2,3])
    assert False, "Should have raised"
except ValidationError:
    pass
print("22. ActionValidator invalid target: OK")

# ── LLM ──
from app.llm.client import LLMRequest, LLMResponse
from app.llm.adapter import AdapterConfig, OpenAIAdapter, ClaudeAdapter, create_adapter, ADAPTER_MAP
from app.llm.retry import RetryPolicy, RetryHandler

req = LLMRequest(messages=[{"role": "user", "content": "test"}], model="gpt-4o")
assert req.model == "gpt-4o"
assert req.json_mode is True
print("23. LLMRequest: OK")

assert "openai" in ADAPTER_MAP
assert "claude" in ADAPTER_MAP
print("24. ADAPTER_MAP: OK")

policy = RetryPolicy(max_retries=3, fallback_model="gpt-3.5-turbo", fallback_provider="openai")
handler = RetryHandler(policy)
assert handler.should_retry("parse_error", 0) is True
assert handler.should_retry("parse_error", 3) is False
assert handler.get_delay(0) == 1.0
assert handler.has_fallback()
print("25. RetryHandler: OK")

# ── PromptBuilder ──
from app.agents.prompts import PromptBuilder
builder = PromptBuilder(rules_text="好人阵营胜利条件：所有狼人被淘汰。")
prompt = builder.build(
    role=create_role("werewolf"),
    personality=Personality(name="狡猾", traits=[PersonalityTrait.DECEPTIVE]),
    memory_text="第1轮：玩家3号被狼人击杀",
    phase_context="当前是白天讨论阶段，请发言。",
    is_alive=True,
    is_sheriff=False,
    thinking_mode=True,
    player_id=1,
    player_name="Alpha",
)
assert "规则层" in prompt
assert "身份层" in prompt
assert "人格层" in prompt
assert "记忆层" in prompt
assert "信息隔离约束" in prompt
assert "thinking" in prompt
assert "Alpha" in prompt
print("26. PromptBuilder full: OK")

prompt2 = builder.build(
    role=create_role("seer"),
    personality=Personality(),
    memory_text="",
    phase_context="请查验一名玩家",
    thinking_mode=False,
    player_id=2,
)
assert "thinking字段" not in prompt2
assert "action" in prompt2
print("27. PromptBuilder no-thinking: OK")

user_prompt = builder.build_user_prompt("当前是投票阶段，请投出你的一票。")
assert "投票阶段" in user_prompt
print("28. PromptBuilder user prompt: OK")

# ── Agent ──
from app.agents.base import Agent
from app.models.player import LLMConfig

agent = Agent(
    player_id=1,
    name="Alpha",
    role=create_role("werewolf"),
    faction=Faction.WOLF,
    is_alive=True,
    llm_config=LLMConfig(provider="openai", model_name="gpt-4o"),
    personality=Personality(name="狡猾", traits=[PersonalityTrait.DECEPTIVE]),
)
assert agent.role_name == "狼人"
assert agent.is_wolf is True
assert agent.is_alive is True

agent.add_public_memory("day_1", "speech", "玩家3号说自己是好人")
agent.add_private_memory("night_1", "wolf_action", "我选择击杀玩家5号")
agent.add_faction_memory("night_1", "wolf_discuss", "狼人协商：击杀5号")

wolf_text = agent.get_visible_memory_text()
assert "阵营" in wolf_text
assert "私有" in wolf_text

d = agent.to_dict()
assert d["player_id"] == 1
assert d["faction"] == "wolf"
print("29. Agent: OK")

print()
print("All tests passed!")