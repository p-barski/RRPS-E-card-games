import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { playECardMatchEndSfx } from "../../shared/sfx";
import type { ECardMatchSummary, ECardRound, ECardState } from "../../shared/types";

export type ECardPhase = "idle" | "revealing" | "result" | "discarding" | "match-banner" | "reshuffling";

export interface ECardTableView {
  displayState: ECardState;
  phase: ECardPhase;
  activeRound: ECardRound | null;
  activeMatchSummary: ECardMatchSummary | null;
  hand: ECardState["hand"];
  pending: ECardState["pending"];
}

type ECardEvent =
  | { kind: "round"; round: ECardRound; handAfter: ECardState["hand"] }
  | { kind: "match-end"; summary: ECardMatchSummary; isFinalMatch: boolean };

const REVEAL_MS = 650;
const RESULT_MS = 950;
const DISCARD_MS = 450;
const MATCH_BANNER_MS = 1300;
const RESHUFFLE_MS = 900;

const NO_PENDING: ECardState["pending"] = { "0": null, "1": null };

function initialHandForEmperorSeat(emperorSeat: number): ECardState["hand"] {
  const emperorHand = { citizen: 4, emperor: 1 };
  const slaveHand = { citizen: 4, slave: 1 };
  return emperorSeat === 0 ? { "0": emperorHand, "1": slaveHand } : { "0": slaveHand, "1": emperorHand };
}

function decrementHand(hand: ECardState["hand"], round: ECardRound): ECardState["hand"] {
  return {
    "0": { ...hand["0"], [round.seat0_card]: (hand["0"][round.seat0_card] ?? 0) - 1 },
    "1": { ...hand["1"], [round.seat1_card]: (hand["1"][round.seat1_card] ?? 0) - 1 },
  };
}

/** Same idea as useRPSTable, extended for E-card's match structure: a
 * single websocket update can carry a drawn round-4 plus its auto-resolve
 * (two round events) followed by a match conclusion, so state diffs are
 * turned into a small queue of round/match-end events replayed in order.
 * All side effects (timers, ref bookkeeping) live in plain functions, not
 * inside setState updaters, since React (StrictMode in particular) may
 * invoke an updater function more than once per commit.
 *
 * `hand` can't be read straight off the live socket state: a match-ending
 * move's broadcast already carries the *next* match's freshly-reset hand
 * (the reset happens server-side in the same mutation that closes out the
 * match), and independently the bot can pre-submit a future round's card
 * before the current one has finished animating. Either would make a
 * live-state read jump ahead of what's on screen — showing the new match's
 * hand before its reshuffle animation, or a future round's decrement before
 * that round has even started revealing. So instead each queued round event
 * carries its own precomputed post-round hand (reconstructed from that
 * round's match's starting composition, which is fully determined by which
 * seat was Emperor), and `hand` only ever updates to it when that round
 * actually starts animating. Match-end events intentionally leave `hand`
 * untouched — the reset to the new match's fresh hand only becomes visible
 * once the following round event (or a full catch-up commit) reveals it,
 * i.e. after the banner and reshuffle animation have played out.
 *
 * `pending` has the same displayState-staleness problem for a different
 * reason: once a round is queued, displayState is frozen until the whole
 * batch (round + any match-end) finishes, but that round's own two
 * face-down picks are exactly the pending values from *before* it started —
 * so if, say, the opponent had a card down before this round resolved,
 * `displayState.pending[opponent]` stays truthy all the way through the
 * reveal, the match-won banner, and the reshuffle, making it look like they
 * already have a new card down for a match that hasn't started yet. Once a
 * round starts revealing, both its cards are fully accounted for by
 * `activeRound` instead, so `pending` is cleared right then and stays
 * cleared until a genuine new pending-only move (or a full commit) sets it
 * again. */
export function useECardTable(state: ECardState | null): ECardTableView | null {
  const [display, setDisplay] = useState<ECardState | null>(null);
  const [phase, setPhase] = useState<ECardPhase>("idle");
  const [activeRound, setActiveRound] = useState<ECardRound | null>(null);
  const [activeMatchSummary, setActiveMatchSummary] = useState<ECardMatchSummary | null>(null);
  const [hand, setHand] = useState<ECardState["hand"] | null>(null);
  const [pending, setPending] = useState<ECardState["pending"] | null>(null);

  const displayRef = useRef<ECardState | null>(null);
  const seenMatchesCountRef = useRef(0);
  const seenRoundsInCurrentMatchRef = useRef(0);
  const mySeatRef = useRef(0);
  const queueRef = useRef<ECardEvent[]>([]);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const processingRef = useRef(false);
  const latestStateRef = useRef<ECardState | null>(null);

  useEffect(() => {
    latestStateRef.current = state;
    if (!state) return;
    mySeatRef.current = state.your_seat;

    if (displayRef.current === null) {
      seenMatchesCountRef.current = state.matches_history.length;
      seenRoundsInCurrentMatchRef.current = state.match_rounds.length;
      displayRef.current = state;
      setDisplay(state);
      setHand(state.hand);
      setPending(state.pending);
      return;
    }

    const events = computeEvents(state);
    if (events.length > 0) {
      queueRef.current.push(...events);
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

  function computeEvents(state: ECardState): ECardEvent[] {
    const events: ECardEvent[] = [];
    if (state.matches_history.length > seenMatchesCountRef.current) {
      for (let i = seenMatchesCountRef.current; i < state.matches_history.length; i++) {
        const summary = state.matches_history[i];
        const newRounds = summary.rounds.slice(seenRoundsInCurrentMatchRef.current);
        let running = initialHandForEmperorSeat(summary.emperor_seat);
        summary.rounds.slice(0, seenRoundsInCurrentMatchRef.current).forEach((round) => {
          running = decrementHand(running, round);
        });
        newRounds.forEach((round) => {
          running = decrementHand(running, round);
          events.push({ kind: "round", round, handAfter: running });
        });
        events.push({
          kind: "match-end",
          summary,
          isFinalMatch: state.status === "finished" && i === state.matches_history.length - 1,
        });
        seenRoundsInCurrentMatchRef.current = 0;
      }
      seenMatchesCountRef.current = state.matches_history.length;
    }
    if (state.status === "in_progress") {
      const newMidRounds = state.match_rounds.slice(seenRoundsInCurrentMatchRef.current);
      if (newMidRounds.length > 0) {
        const emperorSeat = state.side_of["0"] === "emperor" ? 0 : 1;
        let running = initialHandForEmperorSeat(emperorSeat);
        state.match_rounds.slice(0, seenRoundsInCurrentMatchRef.current).forEach((round) => {
          running = decrementHand(running, round);
        });
        newMidRounds.forEach((round) => {
          running = decrementHand(running, round);
          events.push({ kind: "round", round, handAfter: running });
        });
      }
      seenRoundsInCurrentMatchRef.current = state.match_rounds.length;
    }
    return events;
  }

  function commitLatest() {
    if (latestStateRef.current) {
      displayRef.current = latestStateRef.current;
      setDisplay(latestStateRef.current);
      setHand(latestStateRef.current.hand);
      setPending(latestStateRef.current.pending);
    }
  }

  function advance() {
    if (queueRef.current.length > 0) {
      processQueue();
    } else {
      commitLatest();
    }
  }

  function processQueue() {
    if (processingRef.current) return;
    const next = queueRef.current.shift();
    if (!next) return;
    processingRef.current = true;

    if (next.kind === "round") {
      setActiveRound(next.round);
      setPhase("revealing");
      setHand(next.handAfter);
      setPending(NO_PENDING);
      timersRef.current.push(
        setTimeout(() => {
          setPhase("result");
          timersRef.current.push(
            setTimeout(() => {
              setPhase("discarding");
              timersRef.current.push(
                setTimeout(() => {
                  // flushSync forces this to actually commit as its own
                  // React update — a plain setState here would just get
                  // batched together with the next tick's update by React's
                  // scheduler, since both land within the same
                  // animation-frame window despite being in separate
                  // setTimeout callbacks. But committing the DOM change
                  // isn't enough on its own: the browser's style/layout
                  // recalc (which is what actually resolves this round's
                  // card back to its resting, transition-less "empty" state,
                  // per the `.card-slot.empty .card-flip { transition: none
                  // }` rule) is lazily batched independently of React's
                  // commits, and will happily skip straight from this
                  // round's "flipped" style to the next update's "placed"
                  // style without ever resolving the empty state in between
                  // if nothing forces it to. Reading offsetHeight forces
                  // exactly that flush.
                  flushSync(() => {
                    setPhase("idle");
                    setActiveRound(null);
                  });
                  void document.body.offsetHeight;
                  processingRef.current = false;
                  // One extra tick so the "idle, no card" frame actually
                  // renders before any new pending card (or the next queued
                  // round/match-end) reappears — otherwise the class change
                  // that un-flips this round's card and the one that reveals
                  // the next pending card land in the same React commit, and
                  // the leftover CSS transitions for both (transform reset +
                  // discard-position reset) play at once instead of a clean
                  // single "place" animation.
                  timersRef.current.push(setTimeout(advance, 0));
                }, DISCARD_MS)
              );
            }, RESULT_MS)
          );
        }, REVEAL_MS)
      );
      return;
    }

    setActiveMatchSummary(next.summary);
    setPhase("match-banner");
    playECardMatchEndSfx(next.summary.winner_seat === mySeatRef.current);
    timersRef.current.push(
      setTimeout(() => {
        if (next.isFinalMatch) {
          setPhase("idle");
          setActiveMatchSummary(null);
          processingRef.current = false;
          advance();
          return;
        }
        setPhase("reshuffling");
        timersRef.current.push(
          setTimeout(() => {
            setPhase("idle");
            setActiveMatchSummary(null);
            processingRef.current = false;
            advance();
          }, RESHUFFLE_MS)
        );
      }, MATCH_BANNER_MS)
    );
  }

  if (!display || !hand || !pending) return null;
  return { displayState: display, phase, activeRound, activeMatchSummary, hand, pending };
}
