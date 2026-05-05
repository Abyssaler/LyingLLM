export interface Provider {
  id: string;
  display_name: string;
  adapter: string;
  is_configured: boolean;
  models: Model[];
}

export interface Model {
  id: string;
  display_name: string;
  capabilities: Record<string, boolean | number | null>;
  defaults: Record<string, any>;
}

export interface GameEvent {
  event_id: number;
  game_id: string;
  round_no: number;
  phase: string;
  event_type: string;
  player_id: number | null;
  visibility: string[];
  data: any;
  timestamp: string;
}

export interface GameSummary {
  game_id: string;
  phase: string;
  round_no: number;
  alive_count: number;
  death_count: number;
  winner: string | null;
  players?: PlayerInfo[];
}

export interface PlayerInfo {
  id: number;
  role: string;
  faction: string;
  alive: boolean;
  is_sheriff: boolean;
}

export interface GameListItem {
  game_id: string;
  phase: string;
  round_no: number;
  alive_count: number;
  death_count: number;
  winner: string | null;
  created_at: string | null;
}
