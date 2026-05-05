import { useEffect, useState } from "react";
import { listGames } from "../api/client";
import { getPhaseName } from "../utils/roles";
import type { GameListItem } from "../types";

export default function History({
  onReplay,
  onBack,
}: {
  onReplay: (gameId: string) => void;
  onBack: () => void;
}) {
  const [games, setGames] = useState<GameListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listGames()
      .then((data) => {
        // Sort by creation time descending
        const sorted = [...data].sort((a, b) => {
          if (!a.created_at) return 1;
          if (!b.created_at) return -1;
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });
        setGames(sorted);
      })
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1>📜 历史对局</h1>
        <button onClick={onBack}>← 返回配置</button>
      </div>

      {loading && <div style={{ color: "var(--text)", textAlign: "center", padding: 40 }}>加载中...</div>}

      {!loading && games.length === 0 && (
        <div style={{ color: "#888", textAlign: "center", padding: 40 }}>
          暂无对局记录
        </div>
      )}

      {!loading && games.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {games.map((g) => (
            <div
              key={g.game_id}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: 16,
                background: "var(--card-bg)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 16,
              }}
            >
              <div style={{ textAlign: "left", flex: 1 }}>
                <div style={{ fontWeight: "bold", fontSize: 16, color: "var(--text-h)", marginBottom: 4 }}>
                  {g.game_id}
                </div>
                <div style={{ fontSize: 13, color: "var(--text)" }}>
                  第 {g.round_no} 轮 · {getPhaseName(g.phase)} ·
                  {" "}
                  <span style={{ color: "#22c55e" }}>存活 {g.alive_count}</span>
                  {" / "}
                  <span style={{ color: "#ef4444" }}>死亡 {g.death_count}</span>
                  {g.winner && (
                    <span style={{ marginLeft: 8, fontWeight: "bold", color: g.winner === "good" ? "#3b82f6" : "#ef4444" }}>
                      🏆 {g.winner === "good" ? "好人胜利" : "狼人胜利"}
                    </span>
                  )}
                </div>
                {g.created_at && (
                  <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>
                    {new Date(g.created_at).toLocaleString("zh-CN")}
                  </div>
                )}
              </div>
              <button
                onClick={() => onReplay(g.game_id)}
                style={{ flexShrink: 0 }}
              >
                ▶️ 回放
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
