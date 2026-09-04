import { useEffect, useState } from "react";
import { isSfxMuted, setSfxMuted, subscribeSfxMuted } from "./sfx";

export function MuteButton() {
  const [muted, setMuted] = useState(isSfxMuted);

  useEffect(() => subscribeSfxMuted(setMuted), []);

  return (
    <button
      className="mute-toggle"
      onClick={() => setSfxMuted(!muted)}
      aria-label={muted ? "Unmute sound effects" : "Mute sound effects"}
      title={muted ? "Unmute sound effects" : "Mute sound effects"}
    >
      {muted ? "🔇" : "🔊"}
    </button>
  );
}
