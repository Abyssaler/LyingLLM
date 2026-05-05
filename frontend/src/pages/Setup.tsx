import { useEffect, useState } from "react";
import { getProviders, validateSetup, createGame, startGame } from "../api/client";

interface SeatConfig {
  player_id: number;
  provider_id: string;
  model_id: string;
}

export default function Setup({
  onStart,
  onHistory,
}: {
  onStart: (gameId: string) => void;
  onHistory: () => void;
}) {
  const [providers, setProviders] = useState<any[]>([]);
  const [seats, setSeats] = useState<SeatConfig[]>(
    Array.from({ length: 12 }, (_, i) => ({
      player_id: i + 1,
      provider_id: "",
      model_id: "",
    }))
  );
  const [validation, setValidation] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getProviders().then(setProviders);
  }, []);

  const availableProviders = providers.filter((p) => p.is_configured);

  const updateSeat = (idx: number, key: keyof SeatConfig, value: string) => {
    const next = [...seats];
    (next[idx] as any)[key] = value;
    if (key === "provider_id") {
      next[idx].model_id = "";
    }
    setSeats(next);
    setValidation(null);
  };

  const fillAll = () => {
    if (!availableProviders.length) return;
    const p = availableProviders[0];
    const m = p.models[0]?.id || "";
    setSeats(seats.map((s) => ({ ...s, provider_id: p.id, model_id: m })));
    setValidation(null);
  };

  const doValidate = async () => {
    const body = {
      players: seats.map((s) => ({
        player_id: s.player_id,
        model_config: s.provider_id
          ? {
              provider_id: s.provider_id,
              model_id: s.model_id,
            }
          : null,
      })),
    };
    const res = await validateSetup(body);
    setValidation(res);
    return res;
  };

  const doCreate = async () => {
    setLoading(true);
    try {
      const v = await doValidate();
      if (!v.ok) {
        setLoading(false);
        return;
      }
      const body = {
        players: seats.map((s) => ({
          player_id: s.player_id,
          model_config: s.provider_id
            ? {
                provider_id: s.provider_id,
                model_id: s.model_id,
              }
            : null,
        })),
      };
      const { game_id } = await createGame(body);
      await startGame(game_id);
      onStart(game_id);
    } catch (e) {
      alert(String(e));
    } finally {
      setLoading(false);
    }
  };

  const allFilled = seats.every((s) => s.provider_id && s.model_id);

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h1>⚔️ LyingLLM 配置</h1>
        <button onClick={onHistory}>📜 历史对局</button>
      </div>
      <p style={{ color: "var(--text)", marginBottom: 16 }}>
        为 12 个座位配置 AI 模型，所有座位填满后方可开始游戏。
      </p>

      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <button onClick={fillAll} disabled={!availableProviders.length}>
          🔧 一键填充全部座位
        </button>
        <button onClick={doValidate}>✅ 校验配置</button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 12,
          marginBottom: 16,
        }}
      >
        {seats.map((s, i) => {
          const prov = providers.find((p) => p.id === s.provider_id);
          const models = prov?.models || [];
          return (
            <div
              key={s.player_id}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 12,
                background: "var(--card-bg)",
                textAlign: "left",
              }}
            >
              <div style={{ fontWeight: "bold", marginBottom: 8, color: "var(--text-h)" }}>
                座位 #{s.player_id}
              </div>
              <div style={{ marginBottom: 8 }}>
                <label style={{ fontSize: 13, display: "block", marginBottom: 4 }}>Provider</label>
                <select
                  style={{ width: "100%" }}
                  value={s.provider_id}
                  onChange={(e) => updateSeat(i, "provider_id", e.target.value)}
                >
                  <option value="">-- 请选择 --</option>
                  {availableProviders.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 13, display: "block", marginBottom: 4 }}>Model</label>
                <select
                  style={{ width: "100%" }}
                  value={s.model_id}
                  onChange={(e) => updateSeat(i, "model_id", e.target.value)}
                  disabled={!s.provider_id}
                >
                  <option value="">-- 请选择 --</option>
                  {models.map((m: any) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          );
        })}
      </div>

      {validation && (
        <div style={{ marginBottom: 16, textAlign: "left" }}>
          {validation.ok ? (
            <div style={{ color: "#22c55e", padding: 12, background: "rgba(34,197,94,0.1)", borderRadius: 6 }}>
              ✅ 校验通过
            </div>
          ) : (
            <div style={{ color: "#ef4444", padding: 12, background: "rgba(239,68,68,0.1)", borderRadius: 6 }}>
              <strong>❌ 错误：</strong>
              <ul style={{ margin: "4px 0 0", paddingLeft: 20 }}>
                {validation.errors.map((e: any, i: number) => (
                  <li key={i}>{e.message}</li>
                ))}
              </ul>
            </div>
          )}
          {validation.warnings?.length > 0 && (
            <div style={{ color: "#f59e0b", padding: 12, background: "rgba(245,158,11,0.1)", borderRadius: 6, marginTop: 8 }}>
              <strong>⚠️ 警告：</strong>
              <ul style={{ margin: "4px 0 0", paddingLeft: 20 }}>
                {validation.warnings.map((w: any, i: number) => (
                  <li key={i}>{w.message}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <button
        onClick={doCreate}
        disabled={loading || !allFilled || (validation && !validation.ok)}
        style={{
          fontSize: 18,
          padding: "10px 32px",
          background: "var(--accent)",
          color: "#fff",
          border: "none",
        }}
      >
        {loading ? "启动中..." : "🚀 开始游戏"}
      </button>
    </div>
  );
}
