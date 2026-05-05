import { useState } from "react";
import { ThemeProvider } from "./context/ThemeContext";
import Setup from "./pages/Setup";
import Game from "./pages/Game";
import History from "./pages/History";

type Page = "setup" | "game" | "history";

function App() {
  const [page, setPage] = useState<Page>("setup");
  const [gameId, setGameId] = useState<string | null>(null);

  const handleStartGame = (id: string) => {
    setGameId(id);
    setPage("game");
  };

  const handleGoHistory = () => setPage("history");
  const handleGoSetup = () => {
    setGameId(null);
    setPage("setup");
  };

  const handleReplay = (id: string) => {
    setGameId(id);
    setPage("game");
  };

  return (
    <ThemeProvider>
      {page === "setup" && (
        <Setup onStart={handleStartGame} onHistory={handleGoHistory} />
      )}
      {page === "game" && gameId && (
        <Game
          gameId={gameId}
          readOnly={false}
          onBack={handleGoSetup}
        />
      )}
      {page === "history" && (
        <History onReplay={handleReplay} onBack={handleGoSetup} />
      )}
    </ThemeProvider>
  );
}

export default App;
