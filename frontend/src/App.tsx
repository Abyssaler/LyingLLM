import { useState } from "react";
import Setup from "./pages/Setup";
import Game from "./pages/Game";

function App() {
  const [gameId, setGameId] = useState<string | null>(null);

  return (
    <div>
      {gameId ? (
        <Game gameId={gameId} />
      ) : (
        <Setup onStart={(id) => setGameId(id)} />
      )}
    </div>
  );
}

export default App;
