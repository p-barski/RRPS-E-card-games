import { useEffect, useState } from "react";
import type { GameType } from "./types";

function RPSRules() {
  return (
    <>
      <h3>Restricted Rock-Paper-Scissors</h3>
      <ul>
        <li>Each player starts with 3 ★ and a hand of 4 rock, 4 paper, and 4 scissors cards.</li>
        <li>Each round, both players secretly pick a card, then both are revealed at once.</li>
        <li>Normal rock-paper-scissors rules decide the round: rock beats scissors, scissors beats paper, paper beats rock.</li>
        <li>A draw (same card) costs nothing — both cards are discarded and play continues.</li>
        <li>A win transfers 1 ★ from the loser to the winner.</li>
        <li>
          The game ends the instant a player reaches 0 ★ (their opponent wins), or once every card has been played
          (12 rounds) — whoever has more ★ wins; equal ★ is a draw.
        </li>
      </ul>
    </>
  );
}

function ECardRules() {
  return (
    <>
      <h3>E-card</h3>
      <ul>
        <li>
          12 matches are played. In each match, one player is the Emperor (hand: 4 Citizen + 1 Emperor) and the other
          is the Slave (hand: 4 Citizen + 1 Slave). Hands reset fresh every match.
        </li>
        <li>Sides swap every 3 matches, so each player spends 6 matches as Emperor and 6 as Slave over the game.</li>
        <li>Each round, one player places a card face-down first, then the other, then both are revealed.</li>
        <li>Citizen vs Citizen — draw, play continues to the next round (up to 4 rounds).</li>
        <li>Emperor vs Citizen, or Citizen vs Slave — the Emperor side wins the match.</li>
        <li>Emperor vs Slave — the Slave side wins the match.</li>
        <li>
          If round 4 is also a draw, only the special cards remain, and the match auto-resolves with no play needed:
          the Slave beats the Emperor.
        </li>
        <li>Winning a match as Emperor scores 1 point; winning as Slave scores 5 points. Points carry over across all 12 matches.</li>
        <li>After match 12, whoever has more total points wins the game; equal points is a draw.</li>
      </ul>
    </>
  );
}

export function RulesContent({ gameType }: { gameType: GameType }) {
  return gameType === "rps" ? <RPSRules /> : <ECardRules />;
}

function useEscapeKey(onClose: () => void) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);
}

export function RulesModal({ gameType, onClose }: { gameType: GameType | "all"; onClose: () => void }) {
  useEscapeKey(onClose);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <button className="modal-close" onClick={onClose} aria-label="Close rules">
          ×
        </button>
        {gameType === "all" ? (
          <>
            <RulesContent gameType="rps" />
            <RulesContent gameType="ecard" />
          </>
        ) : (
          <RulesContent gameType={gameType} />
        )}
      </div>
    </div>
  );
}

export function RulesButton({
  gameType,
  label,
  className,
}: {
  gameType: GameType | "all";
  label?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className={className ?? "rules-toggle"} onClick={() => setOpen(true)}>
        {label ?? "Rules"}
      </button>
      {open && <RulesModal gameType={gameType} onClose={() => setOpen(false)} />}
    </>
  );
}
