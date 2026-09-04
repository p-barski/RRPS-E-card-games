import { useCallback, useEffect, useRef, useState } from "react";
import type { Names, Presence } from "./types";

const WS_BASE = import.meta.env.VITE_WS_BASE ?? "ws://localhost:8000";
const RECONNECT_DELAY_MS = 1000;

export interface GameSocket<T> {
  state: T | null;
  connected: boolean;
  presence: Presence;
  names: Names;
  error: string | null;
  submitMove: (card: string) => void;
}

export function useGameSocket<T>(roomCode: string | null): GameSocket<T> {
  const [state, setState] = useState<T | null>(null);
  const [connected, setConnected] = useState(false);
  const [presence, setPresence] = useState<Presence>({});
  const [names, setNames] = useState<Names>({});
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!roomCode) return;

    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      socket = new WebSocket(`${WS_BASE}/ws/rooms/${roomCode}/`);
      wsRef.current = socket;

      socket.onopen = () => {
        if (!cancelled) setConnected(true);
      };
      socket.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "state") {
          setState(message.state);
          setError(null);
          if (message.connected) setPresence(message.connected);
          if (message.names) setNames((prev) => ({ ...prev, ...message.names }));
        } else if (message.type === "presence") {
          setPresence(message.connected);
          if (message.names) setNames((prev) => ({ ...prev, ...message.names }));
        } else if (message.type === "error") {
          setError(message.message);
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [roomCode]);

  const submitMove = useCallback((card: string) => {
    wsRef.current?.send(JSON.stringify({ type: "submit_move", card }));
  }, []);

  return { state, connected, presence, names, error, submitMove };
}
