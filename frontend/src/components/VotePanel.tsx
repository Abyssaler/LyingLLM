import type { GameEvent } from '../types';

interface VotePanelProps {
  events: GameEvent[];
  round: number;
}

export function VotePanel({ events, round }: VotePanelProps) {
  const voteEvents = events
    .filter((e) => e.event_type === 'vote' && (e.round === round || round === 0))
    .reverse();

  const resultEvents = events
    .filter((e) => e.event_type === 'vote_result' && (e.round === round || round === 0))
    .reverse();

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 bg-slate-700/50 border-b border-slate-600 font-semibold text-white text-sm">
        🗳️ 投票
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {resultEvents.length > 0 && resultEvents.map((event) => (
          <div key={event.event_id} className="bg-amber-900/40 border border-amber-500/40 rounded-lg p-2">
            <div className="text-sm font-semibold text-amber-300">
              投票结果: {(event.data?.result as string) || ''}
            </div>
            {event.data?.eliminated_id && (
              <div className="text-xs text-red-400">
                出局: P{event.data.eliminated_id as number}
              </div>
            )}
            {Array.isArray(event.data?.tied_ids) && (event.data?.tied_ids as number[]).length > 0 && (
              <div className="text-xs text-yellow-400">
                平票: {(event.data?.tied_ids as number[]).map((id) => `P${id}`).join(', ')}
              </div>
            )}
          </div>
        ))}

        {voteEvents.length === 0 && resultEvents.length === 0 ? (
          <div className="text-center text-slate-500 mt-4 text-sm">暂无投票</div>
        ) : (
          voteEvents.map((event) => (
            <div key={event.event_id} className="text-sm text-slate-300 flex gap-2">
              <span className="text-blue-400">P{event.player_id}</span>
              <span>→</span>
              <span className="text-red-400">
                {event.data?.is_abstain ? '弃票' : `P${event.data?.target as number}`}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}