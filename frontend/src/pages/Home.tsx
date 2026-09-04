import { useState } from "react";
import { createRoom, joinRoom } from "../shared/api";
import { RulesButton } from "../shared/Rules";
import type { GameType } from "../shared/types";

const DISPLAY_NAME_STORAGE_KEY = "rrps-ecard-games-display-name";

export function Home({ onEnterRoom }: { onEnterRoom: (gameType: GameType, code: string) => void }) {
  const [gameType, setGameType] = useState<GameType>("rps");
  const [displayName, setDisplayName] = useState(() => localStorage.getItem(DISPLAY_NAME_STORAGE_KEY) ?? "");
  const [joinCode, setJoinCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleCreate(vsBot: boolean) {
    setBusy(true);
    setError(null);
    try {
      const room = await createRoom(gameType, vsBot, displayName);
      onEnterRoom(room.game_type, room.code);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleJoin() {
    const code = joinCode.trim().toUpperCase();
    if (!code) return;
    setBusy(true);
    setError(null);
    try {
      const room = await joinRoom(code, displayName);
      onEnterRoom(room.game_type, room.code);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="home">
      <fieldset className="game-picker">
        <legend>Choose a game</legend>
        <label>
          <input type="radio" checked={gameType === "rps"} onChange={() => setGameType("rps")} />
          Restricted Rock Paper Scissors
        </label>
        <label>
          <input type="radio" checked={gameType === "ecard"} onChange={() => setGameType("ecard")} />
          E-card
        </label>
        <RulesButton gameType="all" />
      </fieldset>

      <input
        className="name-input"
        placeholder="Your name (optional)"
        value={displayName}
        onChange={(e) => {
          setDisplayName(e.target.value);
          localStorage.setItem(DISPLAY_NAME_STORAGE_KEY, e.target.value);
        }}
        maxLength={40}
      />

      <div className="actions">
        <button disabled={busy} onClick={() => handleCreate(true)}>
          Play vs Bot
        </button>
        <button disabled={busy} onClick={() => handleCreate(false)}>
          Create Room
        </button>
      </div>

      <div className="join">
        <input
          placeholder="Room code"
          value={joinCode}
          onChange={(e) => setJoinCode(e.target.value)}
          maxLength={8}
        />
        <button disabled={busy} onClick={handleJoin}>
          Join Room
        </button>
      </div>

      {error && <p className="error">{error}</p>}
    </div>
  );
}
