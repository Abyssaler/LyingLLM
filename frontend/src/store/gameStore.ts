import { create } from 'zustand';
import type { GameState, GameEvent, WSEvent, Phase, Player } from '../types';
import { GameWSClient } from '../api/client';
import * as api from '../api/client';

interface GameStore {
  // Game state
  gameId: string | null;
  game: GameState | null;
  currentPhase: Phase;
  currentRound: number;
  players: Player[];
  winner: string | null;

  // Game flow
  isPlaying: boolean;
  isLoading: boolean;
  error: string | null;

  // Events
  events: GameEvent[];
  lastEventId: number;

  // UI state
  isNightMode: boolean;
  selectedPlayerId: number | null;
  autoMode: boolean;
  ws: GameWSClient | null;

  // Actions
  setGame: (game: GameState) => void;
  setPhase: (phase: Phase, round: number) => void;
  setPlayers: (players: Player[]) => void;
  addEvent: (event: GameEvent) => void;
  setWinner: (winner: string | null) => void;
  setError: (error: string | null) => void;
  setLoading: (loading: boolean) => void;
  setNightMode: (isNight: boolean) => void;
  setSelectedPlayer: (playerId: number | null) => void;
  setAutoMode: (auto: boolean) => void;

  // WebSocket
  connectWS: (gameId: string) => void;
  disconnectWS: () => void;

  // Reset
  reset: () => void;
}

const NIGHT_PHASES: Phase[] = [
  'NIGHT_BEGIN',
  'WOLF_DISCUSS',
  'NIGHT_ACTIONS',
  'DAWN',
];

function isNightPhase(phase: Phase): boolean {
  return NIGHT_PHASES.includes(phase);
}

export const useGameStore = create<GameStore>((set, get) => ({
  gameId: null,
  game: null,
  currentPhase: 'WAITING',
  currentRound: 0,
  players: [],
  winner: null,
  isPlaying: false,
  isLoading: false,
  error: null,
  events: [],
  lastEventId: 0,
  isNightMode: false,
  selectedPlayerId: null,
  autoMode: false,
  ws: null,

  setGame: (game) =>
    set({
      game,
      gameId: game.game_id,
      currentPhase: game.current_phase as Phase,
      currentRound: game.round,
      players: game.players,
      winner: game.winner,
      isPlaying: game.current_phase !== 'WAITING' && game.current_phase !== 'GAME_END' && game.current_phase !== 'ABORTED',
      isNightMode: isNightPhase(game.current_phase as Phase),
    }),

  setPhase: (phase, round) =>
    set({
      currentPhase: phase,
      currentRound: round,
      isNightMode: isNightPhase(phase),
      isPlaying: phase !== 'WAITING' && phase !== 'GAME_END' && phase !== 'ABORTED',
    }),

  setPlayers: (players) => set({ players }),

  addEvent: (event) =>
    set((state) => ({
      events: [...state.events, event],
      lastEventId: Math.max(state.lastEventId, event.event_id),
    })),

  setWinner: (winner) => set({ winner, isPlaying: false }),

  setError: (error) => set({ error }),

  setLoading: (isLoading) => set({ isLoading }),

  setNightMode: (isNightMode) => set({ isNightMode }),

  setSelectedPlayer: (selectedPlayerId) => set({ selectedPlayerId }),

  setAutoMode: (autoMode) => set({ autoMode }),

  connectWS: (gameId) => {
    const state = get();
    if (state.ws) {
      state.ws.disconnect();
    }
    const ws = new GameWSClient(gameId, state.lastEventId);

    ws.on('phase_change', (data) => {
      const phase = (data.data?.to_phase as Phase) || 'WAITING';
      const round = data.round || 0;
      set({ currentPhase: phase, currentRound: round, isNightMode: isNightPhase(phase) });
      api.getGame(gameId).then(setGame).catch(() => {});
    });

    ws.on('game_end', () => {
      set({ isPlaying: false });
      api.getGame(gameId).then(setGame).catch(() => {});
    });

    ws.on('game_paused', () => {
      set({ isPlaying: false });
    });

    ws.on('game_resumed', () => {
      const p = get().currentPhase;
      set({ isPlaying: p !== 'WAITING' && p !== 'GAME_END' && p !== 'ABORTED' });
    });

    ws.on('*', (data) => {
      if (data.event_id != null) {
        const evt: GameEvent = {
          event_id: parseInt(String(data.event_id), 10) || 0,
          schema_version: '1.0',
          game_id: data.game_id || gameId,
          round: data.round || 0,
          phase: data.phase || '',
          event_type: data.event_type,
          player_id: data.player_id ?? null,
          visibility: [],
          data: data.data || {},
          timestamp: new Date().toISOString(),
        };
        set((s) => ({
          events: [...s.events, evt],
          lastEventId: Math.max(s.lastEventId, evt.event_id),
        }));
      }
    });

    ws.connect();
    set({ ws, gameId });

    api.getEvents(gameId, 0).then((events) => {
      const gameEvents: GameEvent[] = events.map((e: any) => ({
        event_id: e.event_id || 0,
        schema_version: e.schema_version || '1.0',
        game_id: e.game_id || gameId,
        round: e.round || 0,
        phase: e.phase || '',
        event_type: e.event_type,
        player_id: e.player_id ?? null,
        visibility: e.visibility || [],
        data: e.data || {},
        timestamp: e.timestamp || new Date().toISOString(),
      }));
      const maxId = gameEvents.reduce((max, e) => Math.max(max, e.event_id), 0);
      set((s) => ({
        events: [...s.events, ...gameEvents],
        lastEventId: Math.max(s.lastEventId, maxId),
      }));
    }).catch(() => {});
  },

  disconnectWS: () => {
    const ws = get().ws;
    if (ws) {
      ws.disconnect();
    }
    set({ ws: null });
  },

  reset: () => {
    const ws = get().ws;
    if (ws) ws.disconnect();
    set({
      gameId: null,
      game: null,
      currentPhase: 'WAITING',
      currentRound: 0,
      players: [],
      winner: null,
      isPlaying: false,
      isLoading: false,
      error: null,
      events: [],
      lastEventId: 0,
      isNightMode: false,
      selectedPlayerId: null,
      autoMode: false,
      ws: null,
    });
  },
}));