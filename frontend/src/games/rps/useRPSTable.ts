import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { playRPSStarLossSfx } from "../../shared/sfx";
import type { RPSRound, RPSState } from "../../shared/types";

export type RPSPhase = "idle" | "revealing" | "result" | "discarding";

export interface RPSTableView {
  displayState: RPSState;
  phase: RPSPhase;
  activeRound: RPSRound | null;
  hand: RPSState["hand"];
  pending: RPSState["pending"];
}

interface QueuedRound {
  round: RPSRound;
  iLost: boolean;
  myStarsAfter: number;
  handAfter: RPSState["hand"];
}

const START_STARS = 3;
const REVEAL_MS = 650;
const RESULT_MS = 950;
const DISCARD_MS = 450;

const NO_PENDING: RPSState["pending"] = { "0": null, "1": null };

const INITIAL_HAND: RPSState["hand"] = {
  "0": { rock: 4, paper: 4, scissors: 4 },
  "1": { rock: 4, paper: 4, scissors: 4 },
};

function decrementHand(hand: RPSState["hand"], round: RPSRound): RPSState["hand"] {
  const card0 = round.seat0_card as keyof RPSState["hand"]["0"];
  const card1 = round.seat1_card as keyof RPSState["hand"]["1"];
  return {
    "0": { ...hand["0"], [card0]: hand["0"][card0] - 1 },
    "1": { ...hand["1"], [card1]: hand["1"][card1] - 1 },
  };
}

// Hand size only ever changes via completed rounds, and every seat starts
// from the same fixed composition — so the hand after the first K rounds is
// a pure function of `history.slice(0, K)` alone. Deriving it this way
// (instead of decrementing forward from whatever `hand` last held) matters
// because the opponent's own pending-move broadcast (before this round
// completed) already commits its own decrement immediately elsewhere below;
// building this round's decrement on top of that same running value would
// double-count that card. Replaying from the fixed start is immune to that
// since it never reads anything the immediate-commit path touched.
function handAfterRounds(rounds: RPSRound[]): RPSState["hand"] {
  return rounds.reduce(decrementHand, INITIAL_HAND);
}

/** Drives the table animation: server state updates land atomically (a
 * round's cards + its resolution arrive in the same message), so this
 * replays that as reveal -> result -> discard locally, only committing
 * `displayState` to the real, post-round state once the sequence finishes.
 * Anything that isn't part of a round resolving (my own pending card,
 * opponent's hidden-card marker) is mirrored through immediately.
 *
 * `hand` is tracked separately from both `displayState.hand` (which only
 * catches up once the whole reveal/result/discard sequence finishes) and
 * the raw socket state (which can race ahead to a future round the bot has
 * already pre-submitted, before that round has even started animating).
 * It's recomputed fresh per round via `handAfterRounds` and only revealed
 * when that round actually starts animating.
 *
 * `pending` has the same displayState-staleness problem, for a subtler
 * reason: a round only ever gets queued once BOTH seats' pending cards are
 * in (that's what completes it), so `displayState.pending[opponent]` is
 * already `true` from before this round even started — reading it straight
 * off displayState keeps the opponent's card-slot continuously "placed"
 * through the whole reveal/discard sequence (it never dips back to empty).
 * That makes the CSS transitions that undo the reveal-flip (transform) and
 * the discard-throw (translate/opacity) fire while the slot is still
 * visible, instead of while it's hidden — which looks like the card flips
 * again right as the next one is placed. So `pending` is cleared the
 * instant a round starts revealing (activeRound covers the slot from then
 * on) and only restored by a genuine new pending-only move or a full
 * commit — letting the slot actually go empty (invisible) for the gap
 * between one round's discard and the next card appearing. */
export function useRPSTable(state: RPSState | null): RPSTableView | null {
  const [display, setDisplay] = useState<RPSState | null>(null);
  const [phase, setPhase] = useState<RPSPhase>("idle");
  const [activeRound, setActiveRound] = useState<RPSRound | null>(null);
  const [hand, setHand] = useState<RPSState["hand"] | null>(null);
  const [pending, setPending] = useState<RPSState["pending"] | null>(null);

  const displayRef = useRef<RPSState | null>(null);
  const animatedCountRef = useRef(0);
  const myStarsRef = useRef(START_STARS);
  const queueRef = useRef<QueuedRound[]>([]);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const processingRef = useRef(false);
  const latestStateRef = useRef<RPSState | null>(null);

  useEffect(() => {
    latestStateRef.current = state;
    if (!state) return;

    if (displayRef.current === null) {
      animatedCountRef.current = state.history.length;
      displayRef.current = state;
      setDisplay(state);
      setHand(state.hand);
      setPending(state.pending);
      return;
    }

    if (state.history.length > animatedCountRef.current) {
      const seenSoFar = animatedCountRef.current;
      const newRounds = state.history.slice(seenSoFar);
      const mySeat = state.your_seat;
      let running = myStarsRef.current;
      const queued: QueuedRound[] = newRounds.map((round, i) => {
        if (round.winner_seat === mySeat) running += 1;
        else if (round.winner_seat !== null) running -= 1;
        return {
          round,
          iLost: round.winner_seat !== null && round.winner_seat !== mySeat,
          myStarsAfter: running,
          handAfter: handAfterRounds(state.history.slice(0, seenSoFar + i + 1)),
        };
      });
      myStarsRef.current = running;
      queueRef.current.push(...queued);
      animatedCountRef.current = state.history.length;
      processQueue();
    } else if (!processingRef.current) {
      displayRef.current = state;
      setDisplay(state);
      setHand(state.hand);
      setPending(state.pending);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  useEffect(() => {
    const timers = timersRef.current;
    return () => timers.forEach(clearTimeout);
  }, []);

  function commitLatest() {
    if (latestStateRef.current) {
      displayRef.current = latestStateRef.current;
      setDisplay(latestStateRef.current);
      setHand(latestStateRef.current.hand);
      setPending(latestStateRef.current.pending);
    }
  }

  function processQueue() {
    if (processingRef.current) return;
    const next = queueRef.current.shift();
    if (!next) return;
    processingRef.current = true;
    setActiveRound(next.round);
    setPhase("revealing");
    setHand(next.handAfter);
    setPending(NO_PENDING);
    timersRef.current.push(
      setTimeout(() => {
        setPhase("result");
        if (next.iLost) playRPSStarLossSfx(next.myStarsAfter);
        timersRef.current.push(
          setTimeout(() => {
            setPhase("discarding");
            timersRef.current.push(
              setTimeout(() => {
                // flushSync forces this to actually commit as its own React
                // update — a plain setState here would just get batched
                // together with the next tick's update by React's
                // scheduler, since both land within the same
                // animation-frame window despite being in separate
                // setTimeout callbacks. But committing the DOM change isn't
                // enough on its own: the browser's style/layout recalc
                // (which is what actually resolves this round's card back
                // to its resting, transition-less "empty" state, per the
                // `.card-slot.empty .card-flip { transition: none }` rule)
                // is lazily batched independently of React's commits, and
                // will happily skip straight from this round's "flipped"
                // style to the next update's "placed" style without ever
                // resolving the empty state in between if nothing forces
                // it to. Reading offsetHeight forces exactly that flush.
                flushSync(() => {
                  setPhase("idle");
                  setActiveRound(null);
                });
                void document.body.offsetHeight;
                processingRef.current = false;
                // One extra tick so the "idle, no card" frame actually
                // renders before any new pending card reappears — otherwise
                // the class change that un-flips this round's card and the
                // one that reveals the next pending card land in the same
                // React commit, and the leftover CSS transitions for both
                // (transform reset + discard-position reset) play at once
                // instead of a clean single "place" animation.
                timersRef.current.push(
                  setTimeout(() => {
                    if (queueRef.current.length > 0) {
                      processQueue();
                    } else {
                      commitLatest();
                    }
                  }, 0)
                );
              }, DISCARD_MS)
            );
          }, RESULT_MS)
        );
      }, REVEAL_MS)
    );
  }

  if (!display || !hand || !pending) return null;
  return { displayState: display, phase, activeRound, hand, pending };
}
