import { useEffect, useState } from "react";
import { joinRoom } from "../../shared/api";
import { fanChipMarginLeft } from "../../shared/cardFan";
import { PresenceBanner, useOpponentPresence } from "../../shared/Presence";
import { RulesButton } from "../../shared/Rules";
import { RPS_BACK_IMAGE, RPS_CARD_IMAGES } from "../../shared/cards";
import type { RPSState, Seat } from "../../shared/types";
import { useGameSocket } from "../../shared/useGameSocket";
import { useRPSTable } from "./useRPSTable";

const CARD_TYPES = ["rock", "paper", "scissors"] as const;

export function RPSGame({ code, onExit }: { code: string; onExit: () => void }) {
  const [joinError, setJoinError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    joinRoom(code, "")
      .then(() => {
        if (!cancelled) setReady(true);
      })
      .catch((e) => {
        if (!cancelled) setJoinError((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  const { state, connected, presence, names, error, submitMove } = useGameSocket<RPSState>(ready ? code : null);
  const table = useRPSTable(state);
  const oppSeatKeyGuess = table ? (String(1 - table.displayState.your_seat) as Seat) : ("1" as Seat);
  const oppName = names[oppSeatKeyGuess] ?? "Anonymous player";
  const { state: oppPresence, toast } = useOpponentPresence(presence, oppSeatKeyGuess, oppName);

  // Show my own card the instant I click it rather than waiting for the
  // server round-trip (which, against a bot, includes its think delay) —
  // cleared as soon as any fresh state arrives, since that's authoritative.
  const [optimisticCard, setOptimisticCard] = useState<string | null>(null);
  useEffect(() => {
    setOptimisticCard(null);
  }, [state]);

  if (joinError) {
    return (
      <div className="game-screen">
        <p className="error">{joinError}</p>
        <button onClick={onExit}>← Home</button>
      </div>
    );
  }

  if (!ready || !table || !state) {
    return (
      <div className="game-screen">
        <p>Connecting…</p>
      </div>
    );
  }

  const { displayState, phase, activeRound, hand, pending } = table;
  const mySeat = displayState.your_seat;
  const oppSeat = mySeat === 0 ? 1 : 0;
  const mySeatKey = String(mySeat) as Seat;
  const oppSeatKey = String(oppSeat) as Seat;
  // `hand` (from useRPSTable) tracks round-by-round in step with the reveal
  // animation, unlike both displayState.hand (which only catches up once
  // the whole reveal/result/discard sequence finishes) and the raw socket
  // state (which can race ahead to a future round the bot has already
  // pre-submitted, before that round has even started animating).
  const myHand = hand[mySeatKey];
  const oppHand = hand[oppSeatKey];
  const oppCardCount = Object.values(oppHand).reduce((a, b) => a + b, 0);
  // `pending` (from useRPSTable), not displayState.pending: a round only
  // gets queued once both seats' pending cards are in, so
  // displayState.pending[opponent] is already true from before this round
  // even started — reading it here would keep the opponent's card-slot
  // looking "placed" continuously through the whole reveal/discard
  // sequence instead of actually going empty in between.
  const myPendingLive = pending[mySeatKey];
  const oppPendingLive = pending[oppSeatKey];

  const resolving = phase !== "idle" && activeRound !== null;
  const myRoundCard = resolving ? (mySeat === 0 ? activeRound.seat0_card : activeRound.seat1_card) : null;
  const oppRoundCard = resolving ? (oppSeat === 0 ? activeRound.seat0_card : activeRound.seat1_card) : null;
  const myCard = resolving ? myRoundCard : (myPendingLive ?? optimisticCard);
  const oppHasCard = resolving || oppPendingLive !== null;

  const winnerThisRound = resolving ? activeRound.winner_seat : null;
  const iWonRound = winnerThisRound === mySeat;
  const isDraw = resolving && winnerThisRound === null;

  return (
    <div className="game-screen rps">
      <div className="screen-header">
        <button className="exit" onClick={onExit}>
          ← Home
        </button>
        <RulesButton gameType="rps" />
      </div>
      <h2>Restricted Rock Paper Scissors</h2>
      <p className="room-code">Room: {code}</p>
      {!connected && <p className="warning">Reconnecting…</p>}
      {error && <p className="error">{error}</p>}

      <PresenceBanner state={oppPresence} toast={toast} code={code} opponentName={oppName} />

      <div className="stars">
        <span>
          {oppName} {"★".repeat(displayState.stars[oppSeatKey])}
        </span>
        <span>You {"★".repeat(displayState.stars[mySeatKey])}</span>
      </div>

      <div className="opponent-hand">
        {Array.from({ length: oppCardCount }, (_, i) => (
          <img
            className="card-chip"
            key={i}
            src={RPS_BACK_IMAGE}
            alt=""
            style={{ marginLeft: fanChipMarginLeft(i, oppCardCount) }}
          />
        ))}
      </div>
      <p className="opponent-hand-count">
        {oppName}: {oppCardCount} card{oppCardCount === 1 ? "" : "s"} left
      </p>

      <div className="table">
        <div className={`player-col opponent ${oppPresence !== "connected" ? "disconnected" : ""}`}>
          <div
            className={`card-slot ${oppHasCard ? "placed" : "empty"} ${resolving ? "flipped" : ""} ${
              phase === "discarding" ? "discarding" : ""
            }`}
          >
            <div className="card-flip">
              <img className="face back" src={RPS_BACK_IMAGE} alt="" />
              <img
                className="face front"
                src={oppRoundCard ? RPS_CARD_IMAGES[oppRoundCard] : RPS_BACK_IMAGE}
                alt="opponent card"
              />
            </div>
          </div>
          <span className="label">{oppName}</span>
        </div>

        {phase === "result" && (
          <div className="result-overlay">
            {isDraw ? (
              <span className="result-banner draw">DRAW</span>
            ) : (
              <span className={`star-fly ${iWonRound ? "to-right" : "to-left"}`}>★</span>
            )}
          </div>
        )}

        <div className="player-col you">
          <div className={`card-slot ${myCard ? "placed" : "empty"} ${phase === "discarding" ? "discarding" : ""}`}>
            <div className="card-flip static">
              <img className="face front" src={myCard ? RPS_CARD_IMAGES[myCard] : RPS_BACK_IMAGE} alt="your card" />
            </div>
          </div>
          <span className="label">You</span>
        </div>
      </div>

      {displayState.rounds_played > 0 && (
        <div className="discard-pile" key={displayState.rounds_played}>
          <img src={RPS_BACK_IMAGE} alt="" />
          <span>{displayState.rounds_played} played</span>
        </div>
      )}

      {displayState.status === "finished" ? (
        <div className="result">
          {displayState.winner_seat === null
            ? "Draw!"
            : displayState.winner_seat === mySeat
              ? "You win!"
              : "You lose."}
        </div>
      ) : (
        <div className="hand">
          {CARD_TYPES.map((card) => (
            <button
              key={card}
              disabled={phase !== "idle" || myPendingLive !== null || optimisticCard !== null || myHand[card] <= 0}
              onClick={() => {
                setOptimisticCard(card);
                submitMove(card);
              }}
            >
              <img src={RPS_CARD_IMAGES[card]} alt={card} />
              <span>{myHand[card]}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
