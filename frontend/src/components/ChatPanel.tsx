import type { GameEvent } from '../types';

interface ChatPanelProps {
  events: GameEvent[];
  round: number;
}

export function ChatPanel({ events, round }: ChatPanelProps) {
  const speechEvents = events
    .filter((e) => e.event_type === 'speech' || e.event_type === 'last_words' || e.event_type === 'tie_speech')
    .filter((e) => e.round === round || round === 0)
    .reverse();

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 bg-slate-700/50 border-b border-slate-600 font-semibold text-white text-sm">
        💬 发言记录
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {speechEvents.length === 0 ? (
          <div className="text-center text-slate-500 mt-4 text-sm">暂无发言</div>
        ) : (
          speechEvents.map((event) => (
            <div key={event.event_id} className="bg-slate-700/50 rounded-lg p-2">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-blue-400 font-semibold text-sm">P{event.player_id}</span>
                <span className="text-xs text-slate-500">
                  {event.event_type === 'last_words' ? '遗言' : event.event_type === 'tie_speech' ? '平票发言' : '发言'}
                </span>
              </div>
              <div className="text-slate-300 text-sm">
                {(event.data?.content as string) || ''}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}