import { useEffect, useState } from "react";
import { joinRoom } from "../../shared/api";
import { fanChipMarginLeft } from "../../shared/cardFan";
import { PresenceBanner, useOpponentPresence } from "../../shared/Presence";
import { RulesButton } from "../../shared/Rules";
import { ECARD_BACK_IMAGE, ECARD_CARD_IMAGES } from "../../shared/cards";
import { playECardSpecialCardSfx } from "../../shared/sfx";
import type { ECardState, Seat } from "../../shared/types";
import { useGameSocket } from "../../shared/useGameSocket";
import { useECardTable } from "./useECardTable";

export function ECardGame({ code, onExit }: { code: string; onExit: () => void }) {
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

  const { state, connected, presence, names, error, submitMove } = useGameSocket<ECardState>(ready ? code : null);
  const table = useECardTable(state);
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

  const { displayState, phase, activeRound, activeMatchSummary, hand, pending } = table;
  const mySeat = displayState.your_seat;
  const oppSeat = mySeat === 0 ? 1 : 0;
  const mySeatKey = String(mySeat) as Seat;
  const oppSeatKey = String(oppSeat) as Seat;
  const mySide = displayState.side_of[mySeatKey];
  // `hand` (from useECardTable) tracks round-by-round in step with the
  // reveal animation, unlike both displayState.hand (which only catches up
  // once the whole reveal/result/discard, or match-banner/reshuffle,
  // sequence finishes) and the raw socket state (which can race ahead to a
  // future round or even the next match's freshly-reset hand — the server
  // resets hands in the same broadcast that closes out a match, well
  // before that match's banner/reshuffle has played on screen).
  const myHand = hand[mySeatKey];
  const oppHand = hand[oppSeatKey];
  const oppCardCount = Object.values(oppHand).reduce((a, b) => a + b, 0);
  // `pending` (from useECardTable), not displayState.pending: once a round
  // starts revealing, its own two picks are already shown via activeRound,
  // and displayState stays frozen at its pre-round values all the way
  // through any match-banner/reshuffle that follows — reading it here would
  // make an already-resolved pending card (e.g. the opponent moved first
  // last round) look like it's already down for a match that hasn't
  // started yet.
  const myPendingLive = pending[mySeatKey];
  const oppPendingLive = pending[oppSeatKey];
  const idle = phase === "idle";
  const myTurn =
    idle &&
    displayState.status === "in_progress" &&
    myPendingLive === null &&
    optimisticCard === null &&
    isMyTurn(displayState, mySeat);
  const availableCards = Object.entries(myHand)
    .filter(([, count]) => count > 0)
    .map(([card]) => card);

  const showingRound = (phase === "revealing" || phase === "result" || phase === "discarding") && activeRound !== null;
  const myRoundCard = showingRound ? (mySeat === 0 ? activeRound!.seat0_card : activeRound!.seat1_card) : null;
  const oppRoundCard = showingRound ? (oppSeat === 0 ? activeRound!.seat0_card : activeRound!.seat1_card) : null;
  const myCard = showingRound ? myRoundCard : (myPendingLive ?? optimisticCard);
  const oppHasCard = showingRound || oppPendingLive !== null;
  const roundIsDraw = showingRound && activeRound!.winner_seat === null;

  const matchWinningSide =
    activeMatchSummary && activeMatchSummary.winner_seat === activeMatchSummary.emperor_seat ? "Emperor" : "Slave";
  const iWonMatch = activeMatchSummary?.winner_seat === mySeat;

  return (
    <div className="game-screen ecard">
      <div className="screen-header">
        <button className="exit" onClick={onExit}>
          ← Home
        </button>
        <RulesButton gameType="ecard" />
      </div>
      <h2>E-card</h2>
      <p className="room-code">Room: {code}</p>
      {!connected && <p className="warning">Reconnecting…</p>}
      {error && <p className="error">{error}</p>}

      <PresenceBanner state={oppPresence} toast={toast} code={code} opponentName={oppName} />

      <div className="scoreboard">
        <span>Match {Math.min(displayState.match_number, 12)} / 12</span>
        <span>You are: {mySide}</span>
        <span>
          {oppName} points: {displayState.total_points[oppSeatKey]}
        </span>
        <span>Your points: {displayState.total_points[mySeatKey]}</span>
      </div>

      <div className="opponent-hand">
        {Array.from({ length: oppCardCount }, (_, i) => (
          <img
            className="card-chip"
            key={i}
            src={ECARD_BACK_IMAGE}
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
            className={`card-slot ${oppHasCard ? "placed" : "empty"} ${showingRound ? "flipped" : ""} ${
              phase === "discarding" ? "discarding" : ""
            }`}
          >
            <div className="card-flip">
              <img className="face back" src={ECARD_BACK_IMAGE} alt="" />
              <img
                className="face front"
                src={oppRoundCard ? ECARD_CARD_IMAGES[oppRoundCard] : ECARD_BACK_IMAGE}
                alt="opponent card"
              />
            </div>
          </div>
          <span className="label">{oppName}</span>
        </div>

        {phase === "result" && roundIsDraw && (
          <div className="result-overlay">
            <span className="result-banner draw">DRAW</span>
          </div>
        )}
        {phase === "match-banner" && activeMatchSummary && (
          <div className="result-overlay">
            <span className={`result-banner ${iWonMatch ? "good" : "bad"}`}>{matchWinningSide} wins!</span>
          </div>
        )}
        {phase === "reshuffling" && (
          <div className="result-overlay">
            <span className="reshuffle-banner">🔀 Reshuffling deck…</span>
          </div>
        )}

        <div className="player-col you">
          <div className={`card-slot ${myCard ? "placed" : "empty"} ${phase === "discarding" ? "discarding" : ""}`}>
            <div className="card-flip static">
              <img className="face front" src={myCard ? ECARD_CARD_IMAGES[myCard] : ECARD_BACK_IMAGE} alt="your card" />
            </div>
          </div>
          <span className="label">You</span>
        </div>
      </div>

      {displayState.status === "finished" ? (
        <div className="result">
          {displayState.winner_seat === null
            ? "Draw!"
            : displayState.winner_seat === mySeat
              ? "You win!"
              : "You lose."}
        </div>
      ) : myTurn ? (
        <div className="hand">
          {availableCards.map((card) => (
            <button
              key={card}
              onClick={() => {
                setOptimisticCard(card);
                if (card === "emperor" || card === "slave") playECardSpecialCardSfx();
                submitMove(card);
              }}
            >
              <img src={ECARD_CARD_IMAGES[card]} alt={card} />
              <span>{myHand[card]}</span>
            </button>
          ))}
        </div>
      ) : (
        <p>Waiting for {oppName}…</p>
      )}
    </div>
  );
}

function isMyTurn(state: ECardState, seat: number): boolean {
  const first = state.round_number % 2 === 1 ? state.match_first_picker : 1 - state.match_first_picker;
  const firstKey = String(first) as Seat;
  const turn = state.pending[firstKey] === null ? first : 1 - first;
  return turn === seat;
}
