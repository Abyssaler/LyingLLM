import sys
sys.path.insert(0, '.')

from app.rules.manager import RuleConfig, RuleManager
from app.config.loader import YAMLLoader
from app.storage.game_log import GameLogStorage
from app.models.event import (
    DeathCause, DeathRecord, NightActionSet, NightResolutionResult,
    PrivateResult, VoteRecord, VoteResult, VoteSummary, EventVisibility,
)
from app.models.game import Game, GameConfig
from app.models.player import Player, PlayerStatus, LLMConfig
from app.models.role import Faction
from app.core.engine import GameEngine, NightActionCollector, WolfDiscussResult
from app.core.state import GameStateMachine, InvalidTransitionError
from app.core.phase import Phase
from app.agents.judge import JudgeConfig

# ── RuleConfig ──
loader = YAMLLoader()
rm = RuleManager(loader)
rules = rm.load("classic")

assert rules.name == "经典狼人杀"
assert rules.enable_sheriff is True
assert rules.enable_last_words is True
assert rules.enable_wolf_discuss is True
assert rules.night_order == ["guard", "werewolf", "witch", "seer"]
assert rules.witch_can_self_save is False
assert rules.hunter_can_shoot_on_witch_kill is True
assert rules.guard_cannot_guard_same_twice is True
assert rules.guard_blocks_wolf_kill is True
assert rules.witch_save_blocks_wolf_kill is True
assert rules.guard_witch_same_target_dies is True
assert rules.merge_death_causes is True
assert rules.first_night_has_last_words is True
assert rules.mvp_include_dead_players is True
assert rules.sheriff_can_transfer is True
assert rules.vote_type == "majority"
assert rules.tie_handling == "revote"
assert rules.max_revote_rounds == 2
assert rules.final_tie_resolution == "no_elimination"
assert rules.sheriff_vote_weight == 1.5
assert rules.allow_abstain is True
assert rules.get_role_range("werewolf") == (2, 4)
assert rules.get_role_range("seer") == (1, 1)
assert rules.validate_player_count(9) is True
print("1. RuleConfig: OK")

# ── GameLogStorage ──
log = GameLogStorage(game_id="test_game_001")
log.set_config({"players": 9, "rules": "classic"})

# Add various events
log.add_phase_change_event("WAITING", "NIGHT_BEGIN", 1)
log.add_night_event("wolf_discuss_result", "night_1", 1, data={"target": 3, "votes": {1: 3, 2: 3}})
log.add_night_action_event("night_1", 1, 5, "guard", "guard", target_id=3)
log.add_thinking_event("night_1", 1, 3, "I think player 5 is suspicious...")
log.add_speech_event("day_1_discuss", 1, 3, "I think player 5 is suspicious")

# Test private result event
log.add_private_result_event("night_1", 1, 4, "seer_check", {"target": 5, "is_wolf": True})

# Test death event
log.add_death_event("night_1", 1, [DeathRecord(player_id=3, causes=[DeathCause.WOLF_KILL])], "玩家3号昨晚死亡")
log.add_last_words_event("day_1", 1, 3, "我是好人...")
log.add_vote_event("day_1_vote", 1, 1, target_id=5)
log.add_vote_result_event("day_1_vote_result", 1, VoteSummary(
    round=1, votes=[VoteRecord(voter_id=1, target_id=5)], result=VoteResult.MAJORITY, eliminated_id=5
))
log.add_on_death_skill_event("on_death_skill", 1, 5, "shoot", target_id=7)

# Build log
game_log = log.build_log()
assert game_log.game_id == "test_game_001"
assert len(game_log.day_log) > 0
assert len(game_log.observer_log) > 0
assert len(game_log.private_events) > 0
print("2. GameLogStorage events: OK")

# Test night resolution
nc = NightActionCollector(round=1)
nc.guard_target = 3
nc.wolf_kill_target = 5
nc.seer_check_target = 2
nc.has_guard_action = True
nc.has_seer_action = True

action_set = nc.to_action_set()
assert action_set.round == 1
assert action_set.guard_target == 3
assert action_set.wolf_kill_target == 5
assert action_set.seer_check_target == 2
print("3. NightActionCollector: OK")

# Test resolution with default rules
resolution = NightResolutionResult(
    deaths=[DeathRecord(player_id=5, causes=[DeathCause.WOLF_KILL])],
    death_causes=[DeathRecord(player_id=5, causes=[DeathCause.WOLF_KILL])],
    private_results=[PrivateResult(player_id=2, result_type="seer_check", data={"target": 5, "is_wolf": False})],
    public_announcement="昨夜，玩家5号死亡。",
)
assert len(resolution.deaths) == 1
assert resolution.deaths[0].player_id == 5
print("4. NightResolutionResult: OK")

# ── GameLogStorage save/load ──
import tempfile, os
with tempfile.TemporaryDirectory() as tmpdir:
    filepath = log.save_to_file(os.path.join(tmpdir, "test_log.json"))
    assert os.path.exists(filepath)
    
    loaded = GameLogStorage.load_from_file(filepath)
    loaded_log = loaded.build_log()
    assert loaded_log.game_id == "test_game_001"
    assert len(loaded_log.day_log) > 0
print("5. GameLogStorage save/load: OK")

# ── VoteSummary counting ──
votes = [
    VoteRecord(voter_id=1, target_id=3, is_abstain=False),
    VoteRecord(voter_id=2, target_id=3, is_abstain=False),
    VoteRecord(voter_id=3, target_id=5, is_abstain=False),
    VoteRecord(voter_id=4, target_id=5, is_abstain=False),
    VoteRecord(voter_id=5, target_id=3, is_abstain=False),
]
# Player 3 gets 3 votes, player 5 gets 2 votes -> 3 wins with majority
engine_test = GameEngine(
    game=Game(config=GameConfig(player_count=5, rules_config="classic")),
    rules_config=rules,
)
# Manually set up 5 alive players
for i in range(1, 6):
    p = Player(player_id=i, name=f"P{i}", status=PlayerStatus.ALIVE, faction=Faction.VILLAGE)
    engine_test.game.players.append(p)

result = engine_test._count_votes(votes)
assert result.result == VoteResult.MAJORITY
assert result.eliminated_id == 3
print("6. Vote counting (majority): OK")

# Test tie
votes_tie = [
    VoteRecord(voter_id=1, target_id=3, is_abstain=False),
    VoteRecord(voter_id=2, target_id=5, is_abstain=False),
]
result_tie = engine_test._count_votes(votes_tie)
assert result_tie.result == VoteResult.TIE
assert 3 in result_tie.tied_ids
assert 5 in result_tie.tied_ids
print("7. Vote counting (tie): OK")

# Test all abstain
votes_abstain = [
    VoteRecord(voter_id=1, target_id=None, is_abstain=True),
    VoteRecord(voter_id=2, target_id=None, is_abstain=True),
]
result_abstain = engine_test._count_votes(votes_abstain)
assert result_abstain.result == VoteResult.ALL_ABSTAIN
print("8. Vote counting (all abstain): OK")

# ── JudgeConfig ──
jc = JudgeConfig(provider="openai", model="gpt-4o", personality="strict")
assert jc.provider == "openai"
assert jc.model == "gpt-4o"
assert jc.mvp_include_dead_players is True
print("9. JudgeConfig: OK")

# ── GameEngine basics ──
game = Game(config=GameConfig(player_count=9, rules_config="classic", enable_sheriff=True))
engine = GameEngine(game=game, rules_config=rules)

# Assign roles
role_assignments = {1: "werewolf", 2: "werewolf", 3: "seer", 4: "witch", 5: "hunter", 6: "guard", 7: "villager", 8: "villager", 9: "villager"}
for i in range(1, 10):
    player = Player(player_id=i, name=f"P{i}", faction=Faction.VILLAGE)
    game.players.append(player)
engine.assign_roles(role_assignments)
engine.create_agents()

# Check wolves
wolves = game.get_alive_wolves()
assert len(wolves) == 2
print("10. GameEngine setup: OK")

# Test win check logic - no wolves eliminated
result = engine._resolve_night()
# Wolves attack, so there should be deaths if night actions were collected
print(f"11. Night resolution: deaths={len(result.deaths)}, announcement='{result.public_announcement[:20]}...'")

# ── _has_wolves ──
assert engine._has_wolves() is True
# Kill off wolves
for pid in [1, 2]:
    game.get_player(pid).status = PlayerStatus.DEAD
    engine.agents[pid].is_alive = False
assert engine._has_wolves() is False
print("12. Win check - no wolves: OK")

# ── Speech order ──
for pid in [1, 2]:
    game.get_player(pid).status = PlayerStatus.ALIVE
    engine.agents[pid].is_alive = True
order = engine._determine_speech_order()
assert len(order) > 0
# All ordered players should be alive
for pid in order:
    p = game.get_player(pid)
    assert p is not None
    assert p.is_alive
print("13. Speech order: OK")

# ── Events after ID ──
events = log.get_events_after(0)
assert len(events) > 0
print(f"14. Events after ID 0: {len(events)} events")

# ── RuleConfig to_dict ──
rd = rules.to_dict()
assert "name" in rd
assert "special_rules" in rd
print("15. RuleConfig.to_dict: OK")

# ── RuleManager caching ──
rules2 = rm.get("classic")
assert rules2 is rules  # same instance, cached
print("16. RuleManager caching: OK")

rm_list = rm.list_available()
assert "classic" in rm_list
print("17. RuleManager.list_available: OK")

print()
print("All tests passed!")