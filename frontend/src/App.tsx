import { BrowserRouter, Routes, Route } from 'react-router-dom';
import SetupPage from './pages/Setup';
import GamePage from './pages/Game';
import HistoryPage from './pages/History';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SetupPage />} />
        <Route path="/game" element={<GamePage />} />
        <Route path="/game/:gameId" element={<GamePage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;