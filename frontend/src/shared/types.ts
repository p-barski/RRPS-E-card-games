export type Seat = "0" | "1";
export type GameType = "rps" | "ecard";

// A seat missing from this map hasn't joined the room at all; present but
// `false` means it joined and then dropped its websocket connection.
export type Presence = Partial<Record<Seat, boolean>>;

// A seat missing from this map hasn't joined the room at all yet.
export type Names = Partial<Record<Seat, string>>;

export interface RoomInfo {
  code: string;
  game_type: GameType;
  status: "waiting" | "active" | "finished";
  seat: number;
  player_count: number;
}

export interface RPSRound {
  seat0_card: string;
  seat1_card: string;
  winner_seat: number | null;
}

export interface RPSState {
  stars: Record<Seat, number>;
  hand: Record<Seat, Record<"rock" | "paper" | "scissors", number>>;
  pending: Record<Seat, string | null>;
  rounds_played: number;
  history: RPSRound[];
  status: "in_progress" | "finished";
  winner_seat: number | null;
  your_seat: number;
}

export interface ECardRound {
  round_number: number;
  seat0_card: string;
  seat1_card: string;
  winner_seat: number | null;
  auto_resolved?: boolean;
}

export interface ECardMatchSummary {
  match_number: number;
  emperor_seat: number;
  winner_seat: number;
  points_awarded: number;
  rounds: ECardRound[];
}

export interface ECardState {
  total_points: Record<Seat, number>;
  match_number: number;
  side_of: Record<Seat, "emperor" | "slave">;
  match_first_picker: number;
  round_number: number;
  pending: Record<Seat, string | null>;
  hand: Record<Seat, Record<string, number>>;
  match_rounds: ECardRound[];
  matches_history: ECardMatchSummary[];
  status: "in_progress" | "finished";
  winner_seat: number | null;
  your_seat: number;
}
