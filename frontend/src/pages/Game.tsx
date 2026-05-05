import { useEffect, useRef, useState } from "react";
import { getGame, getEvents, connectWS } from "../api/client";
import { useTheme } from "../context/ThemeContext";
import { getRoleInfo, getPhaseName } from "../utils/roles";
import type { GameEvent, GameSummary, PlayerInfo } from "../types";

export default function Game({
  gameId,
  readOnly: _readOnly = false,
  onBack,
}: {
  gameId: string;
  readOnly?: boolean;
  onBack?: () => void;
}) {
  const { effectiveTheme, setTheme } = useTheme();
  const [summary, setSummary] = useState<GameSummary | null>(null);
  const [events, setEvents] = useState<GameEvent[]>([]);
  const [lastId, setLastId] = useState(0);
  const [players, setPlayers] = useState<PlayerInfo[]>([]);
  const [expandedReasoning, setExpandedReasoning] = useState<Set<number>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);

  // Initial load
  useEffect(() => {
    let mounted = true;
    const load = async () => {
      const s = await getGame(gameId);
      if (!mounted) return;
      setSummary(s);
      if (s.players) setPlayers(s.players);
      const evs = await getEvents(gameId, 0);
      if (!mounted) return;
      if (evs.length) {
        setEvents(evs);
        setLastId(evs[evs.length - 1].event_id);
      }
    };
    load();
    return () => { mounted = false; };
  }, [gameId]);

  // Polling for readOnly mode or fallback
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      const s = await getGame(gameId);
      if (!mounted) return;
      setSummary(s);
      if (s.players) setPlayers(s.players);
      const evs = await getEvents(gameId, lastId);
      if (!mounted) return;
      if (evs.length) {
        setEvents((prev) => [...prev, ...evs]);
        setLastId(evs[evs.length - 1].event_id);
      }
    };
    const id = setInterval(poll, 2000);
    return () => { mounted = false; clearInterval(id); };
  }, [gameId, lastId]);

  // WebSocket for real-time pushes
  useEffect(() => {
    const ws = connectWS(gameId, lastId);
    ws.onmessage = (msg) => {
      const ev: GameEvent = JSON.parse(msg.data);
      setEvents((prev) => {
        if (prev.find((e) => e.event_id === ev.event_id)) return prev;
        return [...prev, ev];
      });
      setLastId(ev.event_id);
    };
    ws.onerror = (e) => console.error("WS error", e);
    return () => ws.close();
  }, [gameId]);

  // Scroll events to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  // Derive player state from events + summary
  const sheriffId = players.find((p) => p.is_sheriff)?.id ?? null;

  const playerStatus: Record<number, string> = {};
  events.forEach((e) => {
    if (e.event_type === "agent_invocation_start") {
      playerStatus[e.player_id!] = "思考中";
    } else if (e.event_type === "speech") {
      playerStatus[e.player_id!] = "发言中";
    } else if (e.event_type === "night_action" || e.event_type === "vote") {
      playerStatus[e.player_id!] = "已行动";
    }
  });

  // Filter public / observer-visible events for center panel
  const visibleEvents = events.filter((e) =>
    e.visibility.includes("observer") || e.visibility.includes("public")
  );

  const speeches = visibleEvents.filter((e) => e.event_type === "speech");
  const reasoningEvents = visibleEvents.filter((e) => e.event_type === "reasoning_trace");
  const voteEvents = visibleEvents.filter((e) => e.event_type === "vote");
  const nightActions = visibleEvents.filter((e) => e.event_type === "night_action");
  const phaseChanges = events.filter((e) => e.event_type === "phase_change");

  const leftSeats = [1, 2, 3, 4, 5, 6];
  const rightSeats = [7, 8, 9, 10, 11, 12];

  const renderSeatCard = (pid: number) => {
    const p = players.find((x) => x.id === pid);
    const isAlive = p ? p.alive : true;
    const roleInfo = p ? getRoleInfo(p.role) : getRoleInfo("unknown");
    const status = playerStatus[pid] ?? "";
    const isSheriff = sheriffId === pid;

    return (
      <div
        key={pid}
        style={{
          border: `2px solid ${isSheriff ? "#f59e0b" : "var(--border)"}`,
          borderRadius: 10,
          padding: "10px 12px",
          background: isAlive ? "var(--card-bg)" : "#2a2a2a",
          opacity: isAlive ? 1 : 0.5,
          display: "flex",
          alignItems: "center",
          gap: 10,
          transition: "all 0.2s",
          minWidth: 0,
        }}
      >
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: "50%",
            background: isAlive ? "var(--accent-bg)" : "#444",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 18,
            flexShrink: 0,
          }}
        >
          {roleInfo.emoji}
        </div>
        <div style={{ flex: 1, minWidth: 0, textAlign: "left" }}>
          <div style={{ fontWeight: "bold", fontSize: 14, color: isAlive ? "var(--text-h)" : "#888" }}>
            #{pid} {roleInfo.name}
            {isSheriff && " 🏅"}
          </div>
          <div style={{ fontSize: 11, color: status ? "var(--accent)" : "#888", marginTop: 2 }}>
            {isAlive ? status || "闲置" : "已出局"}
          </div>
        </div>
      </div>
    );
  };

  const toggleReasoning = (eventId: number) => {
    setExpandedReasoning((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100svh", overflow: "hidden" }}>
      {/* Top bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 20px",
          borderBottom: "1px solid var(--border)",
          background: "var(--card-bg)",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {onBack && (
            <button onClick={onBack} style={{ padding: "4px 10px" }}>
              ← 返回
            </button>
          )}
          <h1 style={{ fontSize: 20, margin: 0 }}>⚔️ {gameId}</h1>
          {summary && (
            <>
              <span style={{ fontSize: 14, color: "var(--text)" }}>
                第 {summary.round_no} 轮 · {getPhaseName(summary.phase)}
              </span>
              <span style={{ fontSize: 13, color: "#22c55e" }}>
                🟢 存活 {summary.alive_count}
              </span>
              <span style={{ fontSize: 13, color: "#ef4444" }}>
                💀 死亡 {summary.death_count}
              </span>
              {summary.winner && (
                <span style={{ fontSize: 13, color: "#f59e0b", fontWeight: "bold" }}>
                  🏆 胜者: {summary.winner === "good" ? "好人阵营" : "狼人阵营"}
                </span>
              )}
            </>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setTheme(effectiveTheme === "day" ? "night" : "day")}
            style={{ fontSize: 13 }}
          >
            {effectiveTheme === "night" ? "☀️ 日间模式" : "🌙 夜间模式"}
          </button>
        </div>
      </div>

      {/* Main content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden", gap: 12, padding: 12 }}>
        {/* Left seats */}
        <div
          style={{
            width: 220,
            display: "flex",
            flexDirection: "column",
            gap: 8,
            overflowY: "auto",
            flexShrink: 0,
          }}
        >
          {leftSeats.map(renderSeatCard)}
        </div>

        {/* Center info area */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: 12,
            overflow: "hidden",
          }}
        >
          {/* Speeches */}
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              border: "1px solid var(--border)",
              borderRadius: 10,
              padding: 12,
              background: "var(--card-bg)",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <h3 style={{ fontSize: 14, color: "var(--text)", marginBottom: 4 }}>
              💬 公开发言
            </h3>
            {speeches.length === 0 && (
              <div style={{ color: "#888", fontSize: 13, textAlign: "center", padding: 20 }}>
                暂无发言
              </div>
            )}
            {speeches.map((e) => {
              const p = players.find((x) => x.id === e.player_id);
              const roleInfo = p ? getRoleInfo(p.role) : getRoleInfo("unknown");
              return (
                <div
                  key={e.event_id}
                  style={{
                    alignSelf: e.player_id && e.player_id <= 6 ? "flex-start" : "flex-end",
                    maxWidth: "80%",
                    background: e.player_id && e.player_id <= 6
                      ? "var(--accent-bg)"
                      : "rgba(100,100,100,0.1)",
                    border: `1px solid ${e.player_id && e.player_id <= 6 ? "var(--accent-border)" : "var(--border)"}`,
                    borderRadius: 12,
                    padding: "8px 12px",
                    textAlign: "left",
                  }}
                >
                  <div style={{ fontSize: 12, color: "var(--text)", marginBottom: 2 }}>
                    <strong>
                      #{e.player_id} {roleInfo.emoji} {roleInfo.name}
                    </strong>
                    <span style={{ color: "#888", marginLeft: 8 }}>
                      {getPhaseName(e.phase)}
                    </span>
                  </div>
                  <div style={{ fontSize: 14, color: "var(--text-h)" }}>
                    {e.data?.content || e.data?.text || JSON.stringify(e.data)}
                  </div>
                </div>
              );
            })}
            <div ref={bottomRef} />
          </div>

          {/* Reasoning traces */}
          <div
            style={{
              maxHeight: 200,
              overflowY: "auto",
              border: "1px solid var(--border)",
              borderRadius: 10,
              padding: 12,
              background: "var(--card-bg)",
            }}
          >
            <h3 style={{ fontSize: 14, color: "var(--text)", marginBottom: 8 }}>
              🧠 思维过程
            </h3>
            {reasoningEvents.length === 0 && (
              <div style={{ color: "#888", fontSize: 13, textAlign: "center" }}>
                暂无思维记录
              </div>
            )}
            {reasoningEvents.slice(-5).map((e) => {
              const isExpanded = expandedReasoning.has(e.event_id);
              const content = e.data?.content || "";
              return (
                <div
                  key={e.event_id}
                  style={{
                    marginBottom: 6,
                    padding: "6px 10px",
                    background: "var(--code-bg)",
                    borderRadius: 6,
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                  onClick={() => toggleReasoning(e.event_id)}
                >
                  <div style={{ fontSize: 12, color: "var(--accent)" }}>
                    #{e.player_id} · {e.data?.action || "思考"}
                    {isExpanded ? " ▼" : " ▶"}
                  </div>
                  {isExpanded && (
                    <div
                      style={{
                        fontSize: 12,
                        color: "var(--text)",
                        marginTop: 4,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                      }}
                    >
                      {content}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Vote & Night action summary */}
          <div
            style={{
              display: "flex",
              gap: 12,
            }}
          >
            <div
              style={{
                flex: 1,
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: 12,
                background: "var(--card-bg)",
                maxHeight: 160,
                overflowY: "auto",
              }}
            >
              <h3 style={{ fontSize: 14, color: "var(--text)", marginBottom: 6 }}>
                🗳️ 投票记录
              </h3>
              {voteEvents.length === 0 ? (
                <div style={{ color: "#888", fontSize: 12 }}>暂无投票</div>
              ) : (
                voteEvents.slice(-5).map((e) => (
                  <div key={e.event_id} style={{ fontSize: 12, marginBottom: 2, textAlign: "left" }}>
                    第{e.round_no}轮 · #{e.player_id} → #{e.data?.target_id ?? "?"}
                  </div>
                ))
              )}
            </div>
            <div
              style={{
                flex: 1,
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: 12,
                background: "var(--card-bg)",
                maxHeight: 160,
                overflowY: "auto",
              }}
            >
              <h3 style={{ fontSize: 14, color: "var(--text)", marginBottom: 6 }}>
                🌙 夜间行动
              </h3>
              {nightActions.length === 0 ? (
                <div style={{ color: "#888", fontSize: 12 }}>暂无夜间行动</div>
              ) : (
                nightActions.slice(-5).map((e) => (
                  <div key={e.event_id} style={{ fontSize: 12, marginBottom: 2, textAlign: "left" }}>
                    #{e.player_id} · {e.data?.action || "?"}
                    {e.data?.target_id ? ` → #${e.data.target_id}` : ""}
                    {e.data?.result ? ` (${e.data.result})` : ""}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right seats */}
        <div
          style={{
            width: 220,
            display: "flex",
            flexDirection: "column",
            gap: 8,
            overflowY: "auto",
            flexShrink: 0,
          }}
        >
          {rightSeats.map(renderSeatCard)}
        </div>
      </div>

      {/* Bottom timeline */}
      <div
        style={{
          padding: "8px 20px",
          borderTop: "1px solid var(--border)",
          background: "var(--card-bg)",
          flexShrink: 0,
          overflowX: "auto",
        }}
      >
        <div style={{ display: "flex", gap: 16, fontSize: 12, color: "var(--text)", whiteSpace: "nowrap" }}>
          {phaseChanges.length === 0 ? (
            <span style={{ color: "#888" }}>等待游戏开始...</span>
          ) : (
            phaseChanges.map((e) => (
              <span key={e.event_id} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background:
                      e.phase.includes("night") || e.phase.includes("guard") || e.phase.includes("wolf") || e.phase.includes("witch") || e.phase.includes("seer")
                        ? "#6366f1"
                        : "#f59e0b",
                    display: "inline-block",
                  }}
                />
                第{e.round_no}轮·{getPhaseName(e.phase)}
              </span>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
