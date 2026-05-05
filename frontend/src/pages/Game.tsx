import { useEffect, useRef, useState } from "react";
import { getGame, getEvents, connectWS } from "../api/client";
import type { GameEvent, GameSummary } from "../types";

export default function Game({ gameId }: { gameId: string }) {
  const [summary, setSummary] = useState<GameSummary | null>(null);
  const [events, setEvents] = useState<GameEvent[]>([]);
  const [lastId, setLastId] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Initial poll
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      const s = await getGame(gameId);
      if (!mounted) return;
      setSummary(s);
      const evs = await getEvents(gameId, lastId);
      if (!mounted) return;
      if (evs.length) {
        setEvents((prev) => [...prev, ...evs]);
        setLastId(evs[evs.length - 1].event_id);
      }
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, [gameId]);

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

  // Scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const playerStatus: Record<number, string> = {};
  events.forEach((e) => {
    if (e.event_type === "agent_invocation_start") {
      playerStatus[e.player_id!] = "thinking";
    } else if (e.event_type === "speech") {
      playerStatus[e.player_id!] = "speaking";
    } else if (e.event_type === "night_action" || e.event_type === "vote") {
      playerStatus[e.player_id!] = "acted";
    }
  });

  // Build a simple player map from events (role_assignment)
  const roles: Record<number, string> = {};
  const alive: Set<number> = new Set();
  events.forEach((e) => {
    if (e.event_type === "role_assignment") {
      e.data.assignments?.forEach((a: any) => {
        roles[a.player_id] = a.role;
      });
      for (let i = 1; i <= 12; i++) alive.add(i);
    }
    if (e.event_type === "death") {
      alive.delete(e.data.player_id);
    }
  });

  return (
    <div style={{ padding: 16, maxWidth: 1200, margin: "0 auto" }}>
      <h1>
        Game {gameId} — {summary?.phase ?? "..."}
      </h1>
      {summary && (
        <div style={{ marginBottom: 12 }}>
          Round {summary.round_no} | Alive: {summary.alive_count} | Dead:{" "}
          {summary.death_count} | Winner: {summary.winner ?? "—"}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
          marginBottom: 24,
        }}
      >
        {Array.from({ length: 12 }, (_, i) => i + 1).map((pid) => {
          const isAlive = alive.has(pid);
          const role = roles[pid] ?? "?";
          const status = playerStatus[pid] ?? "idle";
          return (
            <div
              key={pid}
              style={{
                border: "1px solid #ccc",
                borderRadius: 8,
                padding: 12,
                opacity: isAlive ? 1 : 0.4,
                background: isAlive ? "#fff" : "#eee",
              }}
            >
              <div style={{ fontWeight: "bold" }}>#{pid}</div>
              <div style={{ fontSize: 12, color: "#666" }}>{role}</div>
              <div style={{ fontSize: 11, marginTop: 4, color: "#888" }}>
                {status}
              </div>
            </div>
          );
        })}
      </div>

      <h2>Event Stream</h2>
      <div
        style={{
          border: "1px solid #ccc",
          borderRadius: 8,
          padding: 12,
          height: 400,
          overflowY: "auto",
          background: "#fafafa",
        }}
      >
        {events.map((e) => (
          <div key={e.event_id} style={{ marginBottom: 6, fontSize: 14 }}>
            <span style={{ color: "#888", fontSize: 12 }}>
              [{e.event_id}] {e.phase}
            </span>{" "}
            <strong>{e.event_type}</strong>{" "}
            {e.player_id ? `(P${e.player_id})` : ""}{" "}
            {e.data ? JSON.stringify(e.data) : ""}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
