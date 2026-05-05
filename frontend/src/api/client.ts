import type { GameState, ModelConfig, WSEvent } from '../types';

const API_BASE = '/api';

export async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export function createGame(body: {
  player_count?: number;
  roles_config?: string;
  rules_config?: string;
  enable_sheriff?: boolean;
  enable_last_words?: boolean;
  role_assignments?: Record<number, string>;
  player_models?: Record<number, { provider: string; model_name: string; base_url?: string; api_key?: string }>;
}) {
  return fetchAPI<GameState>('/games', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function getGame(gameId: string) {
  return fetchAPI<GameState>(`/games/${gameId}`);
}

export function listGames() {
  return fetchAPI<GameState[]>('/games');
}

export function startGame(gameId: string) {
  return fetchAPI<{ game_id: string; current_phase: string; round: number }>(`/games/${gameId}/start`, {
    method: 'POST',
  });
}

export function pauseGame(gameId: string) {
  return fetchAPI<{ game_id: string; current_phase: string }>(`/games/${gameId}/pause`, {
    method: 'POST',
  });
}

export function resumeGame(gameId: string) {
  return fetchAPI<{ game_id: string; current_phase: string }>(`/games/${gameId}/resume`, {
    method: 'POST',
  });
}

export function stopGame(gameId: string) {
  return fetchAPI<{ game_id: string; current_phase: string }>(`/games/${gameId}/stop`, {
    method: 'POST',
  });
}

export function stepGame(gameId: string, request?: { phase?: string; action?: string }) {
  return fetchAPI<Record<string, unknown>>(`/games/${gameId}/step`, {
    method: 'POST',
    body: JSON.stringify(request || {}),
  });
}

export function submitAction(gameId: string, request: { player_id: number; action_type: string; target_id?: number; data?: Record<string, unknown> }) {
  return fetchAPI<Record<string, unknown>>(`/games/${gameId}/action`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export function rerunAction(gameId: string) {
  return fetchAPI<Record<string, unknown>>(`/games/${gameId}/rerun-action`, {
    method: 'POST',
  });
}

export function getMVP(gameId: string) {
  return fetchAPI<{ game_id: string; mvp: { player_id: number; reason: string } | null }>(`/games/${gameId}/mvp`);
}

export function getGameLog(gameId: string) {
  return fetchAPI<Record<string, unknown>>(`/games/${gameId}/log`);
}

export function getDayLog(gameId: string) {
  return fetchAPI<Record<string, unknown>[]>(`/games/${gameId}/log/day`);
}

export function getNightLog(gameId: string) {
  return fetchAPI<Record<string, unknown>[]>(`/games/${gameId}/log/night`);
}

export function getEvents(gameId: string, afterId: number = 0) {
  return fetchAPI<Record<string, unknown>[]>(`/games/${gameId}/events?after_id=${afterId}`);
}

export function getThinking(gameId: string, playerId: number) {
  return fetchAPI<Record<string, unknown>>(`/games/${gameId}/thinking/${playerId}`);
}

export function validateConfig(request: {
  roles_config?: string;
  rules_config?: string;
  player_count?: number;
  model_provider?: string;
}) {
  return fetchAPI<{ valid: boolean; errors: string[]; warnings: string[] }>('/configs/validate', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export function listRoles() {
  return fetchAPI<{ available: string[]; roles: Record<string, unknown> }>('/configs/roles');
}

export function getRoleConfig(name: string) {
  return fetchAPI<Record<string, unknown>>(`/configs/roles/${name}`);
}

export function listRules() {
  return fetchAPI<{ available: string[]; rules: Record<string, unknown> }>('/configs/rules');
}

export function getRuleConfig(name: string) {
  return fetchAPI<Record<string, unknown>>(`/configs/rules/${name}`);
}

export function listModels() {
  return fetchAPI<ModelConfig>('/configs/models');
}

const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_BASE = `${WS_PROTOCOL}//${window.location.host}/api/ws/games`;

export class GameWSClient {
  private ws: WebSocket | null = null;
  private gameId: string;
  private lastEventId: number;
  private handlers: Map<string, Set<(data: WSEvent) => void>> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 2000;

  constructor(gameId: string, lastEventId: number = 0) {
    this.gameId = gameId;
    this.lastEventId = lastEventId;
  }

  connect(): void {
    const url = `${WS_BASE}/${this.gameId}?last_event_id=${this.lastEventId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const data: WSEvent = JSON.parse(event.data);
        if (typeof data.event_id === 'string') {
          const parsed = parseInt(data.event_id, 10);
          if (!Number.isNaN(parsed) && parsed > 0) {
            this.lastEventId = parsed;
          }
        }
        this.emit(data.event_type, data);
        this.emit('*', data);
      } catch {
        // ignore parse errors
      }
    };

    this.ws.onclose = () => {
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), 30000);
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  on(eventType: string, handler: (data: WSEvent) => void): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler);
    return () => this.off(eventType, handler);
  }

  off(eventType: string, handler: (data: WSEvent) => void): void {
    this.handlers.get(eventType)?.delete(handler);
  }

  private emit(eventType: string, data: WSEvent): void {
    this.handlers.get(eventType)?.forEach((h) => h(data));
  }

  send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.handlers.clear();
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  getLastEventId(): number {
    return this.lastEventId;
  }
}
