import { useEffect, useRef, useState } from "react";
import type { Presence, Seat } from "./types";

export type OppPresenceState = "waiting" | "connected" | "disconnected";

export function useOpponentPresence(presence: Presence, oppSeatKey: Seat, opponentName?: string) {
  const value = presence[oppSeatKey];
  const state: OppPresenceState = value === undefined ? "waiting" : value ? "connected" : "disconnected";
  const prevRef = useRef<OppPresenceState>(state);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    const prev = prevRef.current;
    prevRef.current = state;
    if (prev !== "connected" && state === "connected") {
      setToast(`${opponentName ?? "Opponent"} connected!`);
      const t = setTimeout(() => setToast(null), 2400);
      return () => clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  return { state, toast };
}

export function PresenceBanner({
  state,
  toast,
  code,
  opponentName,
}: {
  state: OppPresenceState;
  toast: string | null;
  code: string;
  opponentName?: string;
}) {
  if (state === "waiting") {
    return (
      <p className="presence-banner waiting">
        Waiting for opponent to join — share room code <strong>{code}</strong>
      </p>
    );
  }
  if (state === "disconnected") {
    return (
      <p className="presence-banner disconnected">
        {opponentName ?? "Opponent"} disconnected — waiting for them to reconnect…
      </p>
    );
  }
  if (toast) {
    return <p className="presence-toast">{toast}</p>;
  }
  return null;
}
