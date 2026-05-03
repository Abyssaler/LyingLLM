import { useEffect, useRef } from 'react';
import { useGameStore } from '../store/gameStore';
import { stepGame } from '../api/client';

export function useGameWS(gameId: string | null) {
  const connectWS = useGameStore((s) => s.connectWS);
  const disconnectWS = useGameStore((s) => s.disconnectWS);

  useEffect(() => {
    if (!gameId) return;
    connectWS(gameId);
    return () => {
      disconnectWS();
    };
  }, [gameId, connectWS, disconnectWS]);

  const ws = useGameStore((s) => s.ws);
  return { connected: ws?.connected ?? false };
}

export function useAutoStep(interval: number = 3000) {
  const autoMode = useGameStore((s) => s.autoMode);
  const gameIdRef = useRef(useGameStore.getState().gameId);
  const phaseRef = useRef(useGameStore.getState().currentPhase);

  gameIdRef.current = useGameStore.getState().gameId;
  phaseRef.current = useGameStore.getState().currentPhase;

  useEffect(() => {
    if (!autoMode || interval <= 0) return;

    const id = setInterval(() => {
      const gid = gameIdRef.current;
      const phase = phaseRef.current;
      if (!gid || phase === 'GAME_END' || phase === 'ABORTED' || phase === 'PAUSED') return;
      stepGame(gid).catch(() => {});
    }, interval);

    return () => clearInterval(id);
  }, [autoMode, interval]);
}