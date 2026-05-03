interface NightOverlayProps {
  isNight: boolean;
  onToggle: () => void;
  autoSwitch: boolean;
  onAutoSwitchToggle: () => void;
}

export function NightOverlay({ isNight, onToggle, autoSwitch, onAutoSwitchToggle }: NightOverlayProps) {
  return (
    <div className="fixed inset-0 pointer-events-none z-40 transition-colors duration-1000"
      style={{
        backgroundColor: isNight ? 'rgba(30, 30, 80, 0.25)' : 'rgba(255, 250, 230, 0.08)',
      }}
    />
  );
}

export function NightModeToggle({ isNight, autoSwitch, onToggle, onAutoSwitchToggle }: NightOverlayProps) {
  return (
    <div className="flex items-center gap-3">
      <button
        onClick={onToggle}
        className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
          isNight
            ? 'bg-indigo-600 text-white hover:bg-indigo-500'
            : 'bg-amber-500 text-white hover:bg-amber-400'
        }`}
      >
        {isNight ? '🌙 夜间' : '☀️ 白天'}
      </button>
      <label className="flex items-center gap-1.5 text-sm text-slate-400 cursor-pointer">
        <input
          type="checkbox"
          checked={autoSwitch}
          onChange={onAutoSwitchToggle}
          className="rounded border-slate-500"
        />
        自动切换
      </label>
    </div>
  );
}