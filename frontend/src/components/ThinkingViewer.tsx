import type { GameEvent } from '../types';

interface ThinkingViewerProps {
  events: GameEvent[];
  selectedPlayerId: number | null;
}

export function ThinkingViewer({ events, selectedPlayerId }: ThinkingViewerProps) {
  const thinkingEvents = events
    .filter((e) => e.event_type === 'thinking')
    .filter((e) => selectedPlayerId === null || e.player_id === selectedPlayerId)
    .reverse();

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 bg-slate-700/50 border-b border-slate-600 font-semibold text-white text-sm">
        💭 思维过程{selectedPlayerId !== null ? ` - P${selectedPlayerId}` : ' (全部)'}
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {thinkingEvents.length === 0 ? (
          <div className="text-center text-slate-500 mt-4 text-sm">
            {selectedPlayerId !== null ? '该玩家暂无思维记录' : '暂无思维记录'}
          </div>
        ) : (
          thinkingEvents.map((event) => (
            <div key={event.event_id} className="bg-purple-900/30 border border-purple-500/30 rounded-lg p-2">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-purple-400 font-semibold text-sm">P{event.player_id}</span>
                <span className="text-xs text-slate-500">R{event.round}</span>
              </div>
              <div className="text-slate-300 text-sm italic">
                {(event.data?.thinking as string) || (event.data?.content as string) || '(无内容)'}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}