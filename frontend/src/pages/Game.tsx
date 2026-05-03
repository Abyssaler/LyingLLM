import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useGameStore } from '../store/gameStore';
import { useGameWS, useAutoStep } from '../hooks/useGame';
import * as api from '../api/client';
import { PlayerCard } from '../components/PlayerCard';
import { CenterStage } from '../components/CenterStage';
import { ChatPanel } from '../components/ChatPanel';
import { VotePanel } from '../components/VotePanel';
import { ThinkingViewer } from '../components/ThinkingViewer';
import { NightOverlay, NightModeToggle } from '../components/NightOverlay';
import { Timeline } from '../components/Timeline';
import type { GameEvent } from '../types';

const PHASE_LABELS: Record<string, string> = {
  WAITING: '等待开始',
  SHERIFF_ELECTION: '警长竞选',
  NIGHT_BEGIN: '夜晚开始',
  WOLF_DISCUSS: '狼人协商',
  NIGHT_ACTIONS: '夜间行动',
  DAWN: '天亮了',
  LAST_WORDS: '遗言',
  WIN_CHECK: '胜负判定',
  DISCUSS_ORDER: '确定发言顺序',
  DISCUSS: '白天讨论',
  VOTE: '投票',
  VOTE_RESULT: '投票结果',
  TIE_SPEECH: '平票发言',
  TIE_VOTE: '平票重投',
  EXECUTE: '处决',
  NO_ELIMINATION: '无人出局',
  ON_DEATH_SKILL: '死亡技能',
  GAME_END: '游戏结束',
  PAUSED: '暂停',
  RETRY_OR_FALLBACK: '重试',
  ABORTED: '已终止',
};

export default function GamePage() {
  const { gameId: urlGameId } = useParams<{ gameId?: string }>();
  const storeGameId = useGameStore((s) => s.gameId);
  const gameId = urlGameId || storeGameId;
  const currentPhase = useGameStore((s) => s.currentPhase);
  const currentRound = useGameStore((s) => s.currentRound);
  const players = useGameStore((s) => s.players);
  const winner = useGameStore((s) => s.winner);
  const isPlaying = useGameStore((s) => s.isPlaying);
  const isLoading = useGameStore((s) => s.isLoading);
  const error = useGameStore((s) => s.error);
  const isNightMode = useGameStore((s) => s.isNightMode);
  const autoMode = useGameStore((s) => s.autoMode);
  const events = useGameStore((s) => s.events);
  const selectedPlayerId = useGameStore((s) => s.selectedPlayerId);
  const { setNightMode, setSelectedPlayer, setAutoMode, setGame, setError, setLoading } = useGameStore();

  const [selectedTab, setSelectedTab] = useState<'chat' | 'vote' | 'thinking'>('chat');

  useGameWS(gameId);
  useAutoStep(autoMode ? 3000 : 0);

  useEffect(() => {
    if (!gameId) return;
    api.getGame(gameId).then(setGame).catch(() => {});
  }, [gameId]);

  const handleStep = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      await api.stepGame(gameId);
      const updated = await api.getGame(gameId);
      setGame(updated);
    } catch (e: any) {
      setError(e.message || 'Step failed');
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  const handlePause = useCallback(async () => {
    if (!gameId) return;
    try {
      await api.pauseGame(gameId);
      const updated = await api.getGame(gameId);
      setGame(updated);
    } catch (e: any) {
      setError(e.message);
    }
  }, [gameId]);

  const handleResume = useCallback(async () => {
    if (!gameId) return;
    try {
      await api.resumeGame(gameId);
      const updated = await api.getGame(gameId);
      setGame(updated);
    } catch (e: any) {
      setError(e.message);
    }
  }, [gameId]);

  const handleStop = useCallback(async () => {
    if (!gameId) return;
    try {
      await api.stopGame(gameId);
      const updated = await api.getGame(gameId);
      setGame(updated);
    } catch (e: any) {
      setError(e.message);
    }
  }, [gameId]);

  if (!gameId) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-400">
        <div className="text-center">
          <p className="text-xl mb-4">暂无进行中的游戏</p>
          <a href="/" className="text-blue-400 hover:text-blue-300 underline">返回配置页</a>
        </div>
      </div>
    );
  }

  const phaseLabel = PHASE_LABELS[currentPhase] || currentPhase;

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col">
      <NightOverlay isNight={isNightMode} onToggle={() => setNightMode(!isNightMode)} autoSwitch={true} onAutoSwitchToggle={() => {}} />

      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-600 px-4 py-2 flex items-center justify-between z-50">
        <div className="flex items-center gap-3">
          <a href="/" className="text-lg font-bold text-blue-400 hover:text-blue-300">🐺 LyingLLM</a>
          <span className="text-slate-500">·</span>
          <span className="text-sm text-slate-300">第 {currentRound} 轮</span>
          <span className="text-sm px-2 py-0.5 rounded bg-blue-600/60 text-blue-200">{phaseLabel}</span>
          {winner && (
            <span className="text-sm px-2 py-0.5 rounded bg-green-600/60 text-green-200">
              🏆 {winner === 'village' ? '好人阵营胜利' : '狼人阵营胜利'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <NightModeToggle
            isNight={isNightMode}
            autoSwitch={autoMode}
            onToggle={() => setNightMode(!isNightMode)}
            onAutoSwitchToggle={() => setAutoMode(!autoMode)}
          />
          <button
            onClick={() => setAutoMode(!autoMode)}
            className={`px-3 py-1 rounded text-sm ${autoMode ? 'bg-green-600 hover:bg-green-500' : 'bg-slate-600 hover:bg-slate-500'}`}
          >
            {autoMode ? '⏵ 自动' : '⏸ 手动'}
          </button>
          {!autoMode && (
            <button
              onClick={handleStep}
              disabled={isLoading}
              className="px-3 py-1 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 rounded text-sm"
            >
              {isLoading ? '...' : '▶ 下一步'}
            </button>
          )}
          {currentPhase === 'PAUSED' ? (
            <button onClick={handleResume} className="px-3 py-1 bg-green-600 hover:bg-green-500 rounded text-sm">
              继续
            </button>
          ) : isPlaying && !autoMode ? (
            <button onClick={handlePause} className="px-3 py-1 bg-yellow-600 hover:bg-yellow-500 rounded text-sm">
              暂停
            </button>
          ) : null}
          <button onClick={handleStop} className="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-sm">
            终止
          </button>
        </div>
      </header>

      {error && (
        <div className="bg-red-900/80 text-red-200 px-4 py-2 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left players */}
        <div className="w-48 border-r border-slate-700 p-2 overflow-y-auto">
          <div className="text-xs text-slate-500 uppercase mb-2 text-center">玩家</div>
          <div className="space-y-2">
            {players.slice(0, Math.ceil(players.length / 2)).map((p) => (
              <PlayerCard
                key={p.player_id}
                player={p}
                isCurrentSpeaker={false}
                isSelected={selectedPlayerId === p.player_id}
                onClick={(id) => setSelectedPlayer(id)}
              />
            ))}
          </div>
        </div>

        {/* Center */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <CenterStage
            round={currentRound}
            phase={currentPhase}
            players={players}
            events={events}
            selectedPlayerId={selectedPlayerId}
          />

          {/* Tabs */}
          <div className="border-t border-slate-600">
            <div className="flex bg-slate-800/50">
              <button
                onClick={() => setSelectedTab('chat')}
                className={`flex-1 px-4 py-2 text-sm ${selectedTab === 'chat' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-300'}`}
              >
                💬 发言
              </button>
              <button
                onClick={() => setSelectedTab('vote')}
                className={`flex-1 px-4 py-2 text-sm ${selectedTab === 'vote' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-300'}`}
              >
                🗳️ 投票
              </button>
              <button
                onClick={() => setSelectedTab('thinking')}
                className={`flex-1 px-4 py-2 text-sm ${selectedTab === 'thinking' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-300'}`}
              >
                💭 思维
              </button>
            </div>
            <div className="h-48 overflow-hidden">
              {selectedTab === 'chat' && <ChatPanel events={events} round={currentRound} />}
              {selectedTab === 'vote' && <VotePanel events={events} round={currentRound} />}
              {selectedTab === 'thinking' && <ThinkingViewer events={events} selectedPlayerId={selectedPlayerId} />}
            </div>
          </div>
        </div>

        {/* Right players */}
        <div className="w-48 border-l border-slate-700 p-2 overflow-y-auto">
          <div className="text-xs text-slate-500 uppercase mb-2 text-center">玩家</div>
          <div className="space-y-2">
            {players.slice(Math.ceil(players.length / 2)).map((p) => (
              <PlayerCard
                key={p.player_id}
                player={p}
                isCurrentSpeaker={false}
                isSelected={selectedPlayerId === p.player_id}
                onClick={(id) => setSelectedPlayer(id)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Timeline */}
      <Timeline events={events} currentRound={currentRound} />
    </div>
  );
}