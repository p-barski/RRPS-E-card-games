import type { GameType, RoomInfo } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

export function createRoom(gameType: GameType, vsBot: boolean, displayName: string): Promise<RoomInfo> {
  return apiFetch("/api/rooms/", {
    method: "POST",
    body: JSON.stringify({ game_type: gameType, vs_bot: vsBot, display_name: displayName }),
  });
}

export function joinRoom(code: string, displayName: string): Promise<RoomInfo> {
  return apiFetch(`/api/rooms/${code}/join/`, {
    method: "POST",
    body: JSON.stringify({ display_name: displayName }),
  });
}
