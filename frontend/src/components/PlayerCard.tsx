import type { Player, Faction } from '../types';

const FACTION_ICONS: Record<string, string> = {
  wolf: '🐺',
  village: '🏘️',
};

const ROLE_ICONS: Record<string, string> = {
  werewolf: '🐺',
  villager: '🏘️',
  seer: '🔮',
  witch: '🧙',
  hunter: '🔫',
  guard: '🛡️',
};

interface PlayerCardProps {
  player: Player;
  isCurrentSpeaker: boolean;
  isSelected: boolean;
  onClick: (playerId: number) => void;
}

export function PlayerCard({ player, isCurrentSpeaker, isSelected, onClick }: PlayerCardProps) {
  const statusColor = player.is_alive
    ? 'border-green-500/60 bg-slate-800/90'
    : 'border-red-500/40 bg-slate-900/70 opacity-50';

  const highlightClass = isCurrentSpeaker
    ? 'ring-2 ring-yellow-400 shadow-yellow-400/30'
    : isSelected
      ? 'ring-2 ring-blue-400 shadow-blue-400/30'
      : '';

  const roleIcon = player.role ? ROLE_ICONS[player.role] || '❓' : '❓';
  const factionBadge = player.faction && player.is_alive ? (
    <span className="text-xs px-1 py-0.5 rounded bg-slate-700 text-slate-300">
      {FACTION_ICONS[player.faction] || '?'} {player.faction}
    </span>
  ) : null;

  return (
    <div
      className={`relative flex flex-col items-center gap-1 p-2 rounded-lg border-2 cursor-pointer
        transition-all duration-300 hover:scale-105 ${statusColor} ${highlightClass}`}
      onClick={() => onClick(player.player_id)}
    >
      {player.is_sheriff && (
        <span className="absolute -top-2 -right-2 text-sm">⭐</span>
      )}
      <div className="text-2xl">{player.is_alive ? roleIcon : '💀'}</div>
      <div className="text-sm font-semibold text-slate-200">
        P{player.player_id}
      </div>
      {!player.is_alive && (
        <div className="text-xs text-red-400">出局</div>
      )}
      {player.is_alive && factionBadge}
      {isCurrentSpeaker && (
        <div className="absolute -top-1 -left-1 w-3 h-3 bg-yellow-400 rounded-full animate-pulse" />
      )}
    </div>
  );
}