import { useEffect, useState } from "react";
import { getProviders, validateSetup, createGame, startGame } from "../api/client";

interface SeatConfig {
  player_id: number;
  provider_id: string;
  model_id: string;
}

export default function Setup({ onStart }: { onStart: (gameId: string) => void }) {
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
  };

  const fillAll = () => {
    if (!availableProviders.length) return;
    const p = availableProviders[0];
    const m = p.models[0]?.id || "";
    setSeats(seats.map((s) => ({ ...s, provider_id: p.id, model_id: m })));
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
  };

  const doCreate = async () => {
    setLoading(true);
    try {
      await doValidate();
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

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: "0 auto" }}>
      <h1>LyingLLM Setup</h1>
      <p>Configure 12 seats. Only configured providers are shown.</p>
      <button onClick={fillAll}>Fill all with first provider</button>
      <button onClick={doValidate} style={{ marginLeft: 8 }}>
        Validate
      </button>
      <table style={{ width: "100%", marginTop: 16, borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>Seat</th>
            <th>Provider</th>
            <th>Model</th>
          </tr>
        </thead>
        <tbody>
          {seats.map((s, i) => {
            const prov = providers.find((p) => p.id === s.provider_id);
            const models = prov?.models || [];
            return (
              <tr key={s.player_id} style={{ borderBottom: "1px solid #ccc" }}>
                <td>#{s.player_id}</td>
                <td>
                  <select
                    value={s.provider_id}
                    onChange={(e) => updateSeat(i, "provider_id", e.target.value)}
                  >
                    <option value="">-- select --</option>
                    {availableProviders.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.display_name}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    value={s.model_id}
                    onChange={(e) => updateSeat(i, "model_id", e.target.value)}
                  >
                    <option value="">-- select --</option>
                    {models.map((m: any) => (
                      <option key={m.id} value={m.id}>
                        {m.display_name}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {validation && (
        <div style={{ marginTop: 16 }}>
          {validation.ok ? (
            <span style={{ color: "green" }}>Validation OK</span>
          ) : (
            <div style={{ color: "red" }}>
              <strong>Errors:</strong>
              <ul>
                {validation.errors.map((e: any, i: number) => (
                  <li key={i}>{e.message}</li>
                ))}
              </ul>
            </div>
          )}
          {validation.warnings?.length > 0 && (
            <div style={{ color: "orange" }}>
              <strong>Warnings:</strong>
              <ul>
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
        disabled={loading || (validation && !validation.ok)}
        style={{ marginTop: 16, fontSize: 18, padding: "8px 24px" }}
      >
        {loading ? "Starting..." : "Start Game"}
      </button>
    </div>
  );
}
