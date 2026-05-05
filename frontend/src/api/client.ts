import type { GameListItem } from "../types";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
const WS_BASE = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000/api/ws/games";

export async function getProviders(): Promise<any[]> {
  const r = await fetch(`${BASE}/providers`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function validateSetup(body: any): Promise<any> {
  const r = await fetch(`${BASE}/setup/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function createGame(body: any): Promise<{ game_id: string }> {
  const r = await fetch(`${BASE}/games`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function startGame(gameId: string): Promise<any> {
  const r = await fetch(`${BASE}/games/${gameId}/start`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getGame(gameId: string): Promise<any> {
  const r = await fetch(`${BASE}/games/${gameId}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getEvents(gameId: string, afterId = 0): Promise<any[]> {
  const r = await fetch(`${BASE}/games/${gameId}/events?after_id=${afterId}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listGames(): Promise<GameListItem[]> {
  const r = await fetch(`${BASE}/games`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export function connectWS(gameId: string, lastEventId = 0): WebSocket {
  return new WebSocket(`${WS_BASE}/${gameId}?last_event_id=${lastEventId}`);
}
