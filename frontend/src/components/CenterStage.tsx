import type { GameEvent, Player } from '../types';

interface CenterStageProps {
  round: number;
  phase: string;
  players: Player[];
  events: GameEvent[];
  selectedPlayerId: number | null;
}

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

export function CenterStage({ round, phase, players, events, selectedPlayerId }: CenterStageProps) {
  const recentEvents = events.slice(-20).reverse();

  const aliveCount = players.filter((p) => p.is_alive).length;
  const phaseLabel = PHASE_LABELS[phase] || phase;

  return (
    <div className="flex flex-col h-full">
      {/* Phase header */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-700/50 border-b border-slate-600">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-white">第 {round} 轮</span>
          <span className="text-sm px-2 py-1 rounded bg-blue-600/80 text-blue-100">
            {phaseLabel}
          </span>
        </div>
        <div className="text-sm text-slate-400">
          存活: {aliveCount}/{players.length}
        </div>
      </div>

      {/* Event log */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {recentEvents.length === 0 ? (
          <div className="text-center text-slate-500 mt-8">等待游戏开始...</div>
        ) : (
          recentEvents.map((event, idx) => (
            <EventItem key={`${event.event_id}-${idx}`} event={event} players={players} />
          ))
        )}
      </div>

      {/* Selected player detail */}
      {selectedPlayerId !== null && (
        <PlayerDetailPanel
          player={players.find((p) => p.player_id === selectedPlayerId) || null}
        />
      )}
    </div>
  );
}

function EventItem({ event, players }: { event: GameEvent; players: Player[] }) {
  const player = event.player_id
    ? players.find((p) => p.player_id === event.player_id)
    : null;

  const typeIcons: Record<string, string> = {
    speech: '📢',
    vote: '🗳️',
    vote_result: '🗳️',
    thinking: '💭',
    last_words: '📜',
    deaths: '💀',
    night_action: '🌙',
    wolf_discuss_result: '🐺',
    on_death_skill: '⚔️',
    phase_change: '🔄',
    sheriff_transfer: '⭐',
  };

  const icon = typeIcons[event.event_type] || '📋';
  const playerName = player ? `P${player.player_id}` : '';
  const content = event.event_type === 'speech' || event.event_type === 'last_words'
    ? (event.data?.content as string) || ''
    : event.event_type === 'vote'
      ? `P${event.data?.target as number} ← P${event.player_id}`
      : event.event_type === 'vote_result'
        ? JSON.stringify(event.data)
        : '';

  return (
    <div className="flex items-start gap-2 text-sm">
      <span>{icon}</span>
      {playerName && <span className="text-blue-400 font-semibold">{playerName}</span>}
      <span className="text-slate-300">{content || event.event_type}</span>
    </div>
  );
}

function PlayerDetailPanel({ player }: { player: Player | null }) {
  if (!player) return null;
  return (
    <div className="border-t border-slate-600 p-3 bg-slate-800/60">
      <div className="font-semibold text-white">
        P{player.player_id} - {player.role || '未知角色'}
      </div>
      <div className="text-sm text-slate-400">
        阵营: {player.faction || '未知'} | 状态: {player.is_alive ? '存活' : '出局'}
        {player.is_sheriff ? ' | ⭐ 警长' : ''}
      </div>
    </div>
  );
}