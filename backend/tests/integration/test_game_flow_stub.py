"""Integration test: run a complete game with stub agents."""

import pytest
import pytest_asyncio

from lyingllm.domain.models.game import Phase, GameSetupConfig, PlayerSetupConfig
from lyingllm.domain.models.player import Faction
from lyingllm.engine.runner import GameRunner


def make_setup() -> GameSetupConfig:
    players = [PlayerSetupConfig(player_id=i) for i in range(1, 13)]
    return GameSetupConfig(players=players)


@pytest_asyncio.fixture
async def runner():
    return GameRunner(game_id="stub-1", setup=make_setup(), seed=42)


class TestStubGameFlow:
    @pytest.mark.asyncio
    async def test_game_reaches_game_end(self, runner):
        await runner.run()
        assert runner.state.phase == Phase.GAME_END
        # Must have emitted game_end event
        end_events = [e for e in runner.events.all_events() if e.event_type == "game_end"]
        assert len(end_events) == 1
        winner = end_events[0].data["winner"]
        assert winner in (Faction.VILLAGE.value, Faction.WOLF.value)

    @pytest.mark.asyncio
    async def test_setup_to_role_assignment(self, runner):
        assert runner.state.phase == Phase.SETUP
        await runner.step()
        assert runner.state.phase == Phase.ROLE_ASSIGNMENT

    @pytest.mark.asyncio
    async def test_role_assignment_creates_12_players(self, runner):
        await runner.step()  # SETUP -> ROLE_ASSIGNMENT
        await runner.step()  # ROLE_ASSIGNMENT -> NIGHT_BEGIN
        assert len(runner.state.players) == 12

    @pytest.mark.asyncio
    async def test_first_night_flow(self, runner):
        await runner.step()  # setup
        await runner.step()  # role assignment
        await runner.step()  # night begin (round 1)
        assert runner.state.round_no == 1
        assert runner.state.phase == Phase.GUARD_ACTION

    @pytest.mark.asyncio
    async def test_events_increase(self, runner):
        await runner.run()
        assert len(runner.events.all_events()) > 20

    @pytest.mark.asyncio
    async def test_public_view_does_not_contain_observer_only(self, runner):
        await runner.run()
        public = runner.events.public_view()
        for e in public:
            # night_resolution data may contain causes, but that's public in our impl
            # The key check: reasoning_trace must not be public
            assert e.event_type != "reasoning_trace"

    @pytest.mark.asyncio
    async def test_death_queue_processed(self, runner):
        await runner.run()
        # At least one death should have occurred in a full game
        deaths = [e for e in runner.events.all_events() if e.event_type == "death"]
        assert len(deaths) >= 1

    @pytest.mark.asyncio
    async def test_sheriff_election_on_day1(self, runner):
        await runner.run()
        sheriff_events = [e for e in runner.events.all_events() if e.event_type == "sheriff_result"]
        assert len(sheriff_events) >= 1

    @pytest.mark.asyncio
    async def test_no_crash_on_complete_run(self):
        # Run multiple times with different seeds
        for seed in range(10):
            r = GameRunner(game_id=f"stub-{seed}", setup=make_setup(), seed=seed)
            await r.run()
            assert r.state.phase == Phase.GAME_END
