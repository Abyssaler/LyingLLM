export type Faction = 'wolf' | 'village' | 'other';

export type PlayerStatus = 'alive' | 'dead';

export type Phase =
  | 'WAITING'
  | 'SHERIFF_ELECTION'
  | 'NIGHT_BEGIN'
  | 'WOLF_DISCUSS'
  | 'NIGHT_ACTIONS'
  | 'DAWN'
  | 'LAST_WORDS'
  | 'WIN_CHECK'
  | 'DISCUSS_ORDER'
  | 'DISCUSS'
  | 'VOTE'
  | 'VOTE_RESULT'
  | 'TIE_SPEECH'
  | 'TIE_VOTE'
  | 'EXECUTE'
  | 'NO_ELIMINATION'
  | 'ON_DEATH_SKILL'
  | 'GAME_END'
  | 'PAUSED'
  | 'RETRY_OR_FALLBACK'
  | 'ABORTED';

export type GameEventType =
  | 'game_start'
  | 'game_end'
  | 'game_paused'
  | 'game_resumed'
  | 'game_aborted'
  | 'phase_change'
  | 'state_snapshot'
  | 'sheriff_election'
  | 'sheriff_result'
  | 'night_begin'
  | 'wolf_discuss'
  | 'night_action'
  | 'dawn'
  | 'speech'
  | 'last_words'
  | 'vote'
  | 'vote_result'
  | 'tie_speech'
  | 'tie_vote'
  | 'execute'
  | 'on_death_skill'
  | 'thinking'
  | 'action_retry'
  | 'action_fallback'
  | 'error';

export interface Player {
  player_id: number;
  name: string;
  role: string | null;
  faction: Faction | null;
  status: PlayerStatus;
  is_sheriff: boolean;
  is_alive: boolean;
}

export interface GameConfig {
  player_count: number;
  roles_config: string;
  rules_config: string;
  enable_sheriff: boolean;
  enable_last_words: boolean;
  role_assignments?: Record<number, string>;
  player_models?: Record<number, PlayerModelConfig>;
}

export interface PlayerModelConfig {
  provider: string;
  model_name: string;
  base_url?: string;
  api_key?: string;
}

export interface GameState {
  game_id: string;
  config: GameConfig;
  current_phase: Phase;
  round: number;
  players: Player[];
  sheriff_id: number | null;
  winner: string | null;
  mvp_player_id: number | null;
  mvp_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface GameEvent {
  event_id: number;
  schema_version: string;
  game_id: string;
  round: number;
  phase: string;
  event_type: string;
  player_id: number | null;
  visibility: string[];
  data: Record<string, unknown>;
  timestamp: string;
}

export interface WSEvent {
  event_type: string;
  event_id: string;
  game_id?: string;
  round?: number;
  phase?: string;
  player_id?: number;
  data: Record<string, unknown>;
}

export interface ProviderInfo {
  adapter: string;
  base_url: string;
  default_model: string;
  models: { name: string; max_tokens: number; supports_streaming: boolean; supports_json_mode: boolean }[];
}

export interface ModelConfig {
  name: string;
  version: string;
  description: string;
  providers: Record<string, ProviderInfo>;
  default_provider: string;
  default_model: string;
}

export interface RoleInfo {
  name: string;
  faction: Faction;
  night_priority: number | null;
  description: string;
  prompt_hint: string;
}