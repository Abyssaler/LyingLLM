import type { GameEvent } from '../types';

interface TimelineProps {
  events: GameEvent[];
  currentRound: number;
}

const PHASE_ICONS: Record<string, string> = {
  NIGHT_BEGIN: '🌑',
  WOLF_DISCUSS: '🐺',
  NIGHT_ACTIONS: '🌙',
  DAWN: '🌅',
  LAST_WORDS: '📜',
  DISCUSS: '💬',
  VOTE: '🗳️',
  VOTE_RESULT: '📊',
  EXECUTE: '⚔️',
  GAME_END: '🏁',
};

export function Timeline({ events, currentRound }: TimelineProps) {
  const phaseChanges = events.filter((e) => e.event_type === 'phase_change');

  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-slate-800/80 border-t border-slate-600 overflow-x-auto">
      <span className="text-xs text-slate-500 shrink-0">时间线:</span>
      {phaseChanges.map((event, idx) => {
        const fromPhase = (event.data?.from_phase as string) || '';
        const toPhase = (event.data?.to_phase as string) || '';
        const icon = PHASE_ICONS[toPhase] || '📋';
        const isActive = event.round === currentRound;

        return (
          <div key={event.event_id} className="flex items-center shrink-0">
            {idx > 0 && <span className="text-slate-600 mx-1">→</span>}
            <span
              className={`text-xs px-1.5 py-0.5 rounded ${
                isActive
                  ? 'bg-blue-600/60 text-blue-200'
                  : 'bg-slate-700/60 text-slate-400'
              }`}
            >
              {icon} R{event?.round || 0}
            </span>
          </div>
        );
      })}
      {phaseChanges.length === 0 && (
        <span className="text-xs text-slate-600">等待开始...</span>
      )}
    </div>
  );
}