import { useState, useEffect } from 'react';
import * as api from '../api/client';

interface GameSummary {
  game_id: string;
  current_phase: string;
  round: number;
  player_count: number;
  winner: string | null;
  created_at: string;
}

export default function HistoryPage() {
  const [games, setGames] = useState<GameSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedGameLog, setSelectedGameLog] = useState<Record<string, unknown> | null>(null);
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [logType, setLogType] = useState<'full' | 'day' | 'night'>('full');

  useEffect(() => {
    api.listGames().then((data: any) => {
      setGames(data);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  }, []);

  const handleViewLog = async (gameId: string) => {
    setSelectedGameId(gameId);
    try {
      if (logType === 'day') {
        const log = await api.getDayLog(gameId);
        setSelectedGameLog({ type: 'day', events: log });
      } else if (logType === 'night') {
        const log = await api.getNightLog(gameId);
        setSelectedGameLog({ type: 'night', events: log });
      } else {
        const log = await api.getGameLog(gameId);
        setSelectedGameLog(log);
      }
    } catch {
      setSelectedGameLog({ error: 'Failed to load log' });
    }
  };

  const PHASE_LABELS: Record<string, string> = {
    WAITING: '等待',
    GAME_END: '已结束',
    ABORTED: '已终止',
    PAUSED: '暂停',
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      <h1 className="text-3xl font-bold mb-6 text-center">📋 历史对局</h1>

      <div className="max-w-5xl mx-auto">
        <div className="mb-4 flex items-center gap-4">
          <label className="text-sm text-slate-400">日志类型:</label>
          <select
            value={logType}
            onChange={(e) => setLogType(e.target.value as any)}
            className="bg-slate-700 rounded px-3 py-1 text-sm"
          >
            <option value="full">完整日志</option>
            <option value="day">白天日志</option>
            <option value="night">夜间日志</option>
          </select>
        </div>

        {loading ? (
          <div className="text-center text-slate-500">加载中...</div>
        ) : games.length === 0 ? (
          <div className="text-center text-slate-500 py-8">
            暂无历史对局
            <br />
            <a href="/" className="text-blue-400 hover:text-blue-300 underline">创建新游戏</a>
          </div>
        ) : (
          <div className="space-y-3">
            {games.map((game) => (
              <div
                key={game.game_id}
                className="bg-slate-800 rounded-lg p-4 border border-slate-700 hover:border-slate-500 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm text-slate-400">{game.game_id.slice(0, 12)}...</span>
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        game.winner
                          ? 'bg-green-600/60 text-green-200'
                          : PHASE_LABELS[game.current_phase] === '已结束'
                            ? 'bg-slate-600 text-slate-300'
                            : 'bg-blue-600/60 text-blue-200'
                      }`}>
                        {game.winner
                          ? game.winner === 'village' ? '好人胜' : '狼人胜'
                          : PHASE_LABELS[game.current_phase] || game.current_phase}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      第 {game.round} 轮 · {game.player_count} 人 · {new Date(game.created_at).toLocaleString()}
                    </div>
                  </div>
                  <button
                    onClick={() => handleViewLog(game.game_id)}
                    className="px-4 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-sm"
                  >
                    查看日志
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {selectedGameLog && (
          <div className="mt-6 bg-slate-800 rounded-lg p-4 border border-slate-700">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold">
                对局日志 {selectedGameId && `(${selectedGameId.slice(0, 12)}...)`}
              </h3>
              <button
                onClick={() => setSelectedGameLog(null)}
                className="text-slate-400 hover:text-white text-sm"
              >
                关闭
              </button>
            </div>
            <pre className="bg-slate-900 rounded p-3 overflow-auto max-h-96 text-xs text-slate-300">
              {JSON.stringify(selectedGameLog, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}