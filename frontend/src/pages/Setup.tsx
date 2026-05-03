import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGameStore } from '../store/gameStore';
import * as api from '../api/client';
import type { PlayerModelConfig, GameConfig } from '../types';

interface PlayerSetup {
  name: string;
  model_provider: string;
  model_name: string;
  personality: string;
}

const ROLE_OPTIONS = [
  { key: 'werewolf', label: '狼人 🐺', min: 2, max: 4 },
  { key: 'seer', label: '预言家 🔮', min: 1, max: 1 },
  { key: 'witch', label: '女巫 🧙', min: 1, max: 1 },
  { key: 'hunter', label: '猎人 🔫', min: 0, max: 1 },
  { key: 'guard', label: '守卫 🛡️', min: 0, max: 1 },
  { key: 'villager', label: '村民 🏘️', min: 0, max: 99 },
];

export default function SetupPage() {
  const navigate = useNavigate();
  const { setGame, setError, setLoading, isLoading } = useGameStore();

  const [playerCount, setPlayerCount] = useState(9);
  const [enableSheriff, setEnableSheriff] = useState(true);
  const [enableLastWords, setEnableLastWords] = useState(true);
  const [rolesConfig, setRolesConfig] = useState('classic');
  const [rulesConfig, setRulesConfig] = useState('classic');
  const [playerSetups, setPlayerSetups] = useState<PlayerSetup[]>([]);
  const [roleAssignments, setRoleAssignments] = useState<Record<number, string>>({});
  const [judgeProvider, setJudgeProvider] = useState('openai');
  const [judgeModel, setJudgeModel] = useState('gpt-4o');
  const [availableRoles, setAvailableRoles] = useState<{ key: string; label: string }[]>([]);
  const [availableRules, setAvailableRules] = useState<string[]>([]);
  const [models, setModels] = useState<{ name: string; provider: string }[]>([]);

  useEffect(() => {
    api.listRoles().then((data) => {
      setAvailableRoles(data.available.map((k) => ({ key: k, label: k })));
    }).catch(() => {});
    api.listRules().then((data) => {
      setAvailableRules(data.available);
    }).catch(() => {});
    api.listModels().then((data) => {
      const modelList: { name: string; provider: string }[] = [];
      for (const [provKey, prov] of Object.entries(data.providers || {})) {
        for (const m of (prov as any).models || []) {
          modelList.push({ name: m.name, provider: provKey });
        }
      }
      setModels(modelList);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const setups: PlayerSetup[] = [];
    for (let i = 0; i < playerCount; i++) {
      setups.push({
        name: `P${i + 1}`,
        model_provider: 'openai',
        model_name: 'gpt-4o',
        personality: '',
      });
    }
    setPlayerSetups(setups);
  }, [playerCount]);

  const handleRoleChange = (playerIdx: number, role: string) => {
    setRoleAssignments((prev) => ({ ...prev, [playerIdx + 1]: role }));
  };

  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      const game = await api.createGame({
        player_count: playerCount,
        roles_config: rolesConfig,
        rules_config: rulesConfig,
        enable_sheriff: enableSheriff,
        enable_last_words: enableLastWords,
      });
      setGame(game);
      await api.startGame(game.game_id);
      const updated = await api.getGame(game.game_id);
      setGame(updated);
      navigate(`/game/${game.game_id}`);
    } catch (e: any) {
      setError(e.message || 'Failed to create game');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      <h1 className="text-3xl font-bold mb-6 text-center">🐺 LyingLLM 🏘️</h1>
      <h2 className="text-xl font-semibold mb-4">游戏配置</h2>

      <div className="max-w-4xl mx-auto space-y-6">
        {/* Basic settings */}
        <div className="bg-slate-800 rounded-lg p-4 space-y-4">
          <h3 className="text-lg font-semibold text-slate-300">基本设置</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">玩家数量</label>
              <input
                type="number"
                min={5}
                max={12}
                value={playerCount}
                onChange={(e) => setPlayerCount(parseInt(e.target.value) || 9)}
                className="w-full bg-slate-700 rounded px-3 py-2 text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">角色配置</label>
              <select
                value={rolesConfig}
                onChange={(e) => setRolesConfig(e.target.value)}
                className="w-full bg-slate-700 rounded px-3 py-2 text-white"
              >
                {availableRoles.map((r) => (
                  <option key={r.key} value={r.key}>{r.label}</option>
                ))}
                <option value="classic">经典狼人杀</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">规则配置</label>
              <select
                value={rulesConfig}
                onChange={(e) => setRulesConfig(e.target.value)}
                className="w-full bg-slate-700 rounded px-3 py-2 text-white"
              >
                {availableRules.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
                <option value="classic">经典规则</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableSheriff}
                  onChange={(e) => setEnableSheriff(e.target.checked)}
                />
                启用警长
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableLastWords}
                  onChange={(e) => setEnableLastWords(e.target.checked)}
                />
                启用遗言
              </label>
            </div>
          </div>
        </div>

        {/* Player setup */}
        <div className="bg-slate-800 rounded-lg p-4 space-y-4">
          <h3 className="text-lg font-semibold text-slate-300">玩家配置</h3>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {playerSetups.map((player, idx) => (
              <div key={idx} className="grid grid-cols-4 gap-3 items-end bg-slate-700/50 rounded p-2">
                <div>
                  <label className="block text-xs text-slate-500">名称</label>
                  <input
                    type="text"
                    value={player.name}
                    onChange={(e) => {
                      const newSetups = [...playerSetups];
                      newSetups[idx] = { ...player, name: e.target.value };
                      setPlayerSetups(newSetups);
                    }}
                    className="w-full bg-slate-700 rounded px-2 py-1 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500">模型</label>
                  <select
                    value={player.model_name}
                    onChange={(e) => {
                      const newSetups = [...playerSetups];
                      newSetups[idx] = { ...player, model_name: e.target.value };
                      setPlayerSetups(newSetups);
                    }}
                    className="w-full bg-slate-700 rounded px-2 py-1 text-sm text-white"
                  >
                    {models.map((m) => (
                      <option key={m.name} value={m.name}>{m.name} ({m.provider})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500">角色</label>
                  <select
                    value={roleAssignments[idx + 1] || ''}
                    onChange={(e) => handleRoleChange(idx, e.target.value)}
                    className="w-full bg-slate-700 rounded px-2 py-1 text-sm text-white"
                  >
                    <option value="">自动分配</option>
                    {ROLE_OPTIONS.map((r) => (
                      <option key={r.key} value={r.key}>{r.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500">性格</label>
                  <input
                    type="text"
                    value={player.personality}
                    onChange={(e) => {
                      const newSetups = [...playerSetups];
                      newSetups[idx] = { ...player, personality: e.target.value };
                      setPlayerSetups(newSetups);
                    }}
                    placeholder="如：狡猾策略家"
                    className="w-full bg-slate-700 rounded px-2 py-1 text-sm text-white"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Judge AI */}
        <div className="bg-slate-800 rounded-lg p-4 space-y-4">
          <h3 className="text-lg font-semibold text-slate-300">裁判 AI</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Provider</label>
              <select
                value={judgeProvider}
                onChange={(e) => setJudgeProvider(e.target.value)}
                className="w-full bg-slate-700 rounded px-3 py-2 text-white"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="deepseek">DeepSeek</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Model</label>
              <input
                type="text"
                value={judgeModel}
                onChange={(e) => setJudgeModel(e.target.value)}
                className="w-full bg-slate-700 rounded px-3 py-2 text-white"
              />
            </div>
          </div>
        </div>

        {/* Start button */}
        <div className="text-center">
          <button
            onClick={handleStart}
            disabled={isLoading}
            className="px-8 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-lg text-lg font-semibold transition-colors"
          >
            {isLoading ? '创建中...' : '开始游戏 🚀'}
          </button>
        </div>
      </div>
    </div>
  );
}