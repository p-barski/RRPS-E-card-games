const SFX_FILES = ["/sfx/zawa_1.mp3", "/sfx/zawa_2.mp3", "/sfx/zawa_3.mp3", "/sfx/zawa_4.mp3", "/sfx/zawa_5.mp3"];

const BASE_VOLUME = 0.6;
const VOLUME_JITTER = 0.15; // +/- this fraction of BASE_VOLUME
const PITCH_MIN = 0.9;
const PITCH_MAX = 1.1;
const GAP_MIN_MS = 300;
const GAP_MAX_MS = 600;

const MUTE_STORAGE_KEY = "rrps-ecard-games-sfx-muted";
let muted = localStorage.getItem(MUTE_STORAGE_KEY) === "1";
const muteListeners = new Set<(muted: boolean) => void>();

export function isSfxMuted(): boolean {
  return muted;
}

export function setSfxMuted(value: boolean): void {
  muted = value;
  localStorage.setItem(MUTE_STORAGE_KEY, value ? "1" : "0");
  muteListeners.forEach((listener) => listener(muted));
}

export function subscribeSfxMuted(listener: (muted: boolean) => void): () => void {
  muteListeners.add(listener);
  return () => muteListeners.delete(listener);
}

function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function pickRandomDistinct<T>(items: readonly T[], count: number): T[] {
  const pool = [...items];
  const picked: T[] = [];
  for (let i = 0; i < count && pool.length > 0; i++) {
    const idx = Math.floor(Math.random() * pool.length);
    picked.push(pool.splice(idx, 1)[0]);
  }
  return picked;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Plays one clip and resolves once it's actually finished (or failed to
 * play at all, e.g. blocked by autoplay policy) so callers can tell when
 * it's safe to start the next overlapping-but-still-bounded burst. */
function playOne(src: string): Promise<void> {
  if (muted) return Promise.resolve();
  return new Promise((resolve) => {
    const audio = new Audio(src);
    audio.volume = Math.min(1, Math.max(0, BASE_VOLUME + (Math.random() * 2 - 1) * VOLUME_JITTER));
    audio.playbackRate = PITCH_MIN + Math.random() * (PITCH_MAX - PITCH_MIN);
    const finish = () => resolve();
    audio.addEventListener("ended", finish, { once: true });
    audio.addEventListener("error", finish, { once: true });
    audio.play().catch(finish);
  });
}

// Chains bursts so a new one never starts until the previous burst's last
// clip has actually finished playing, avoiding overlapping "sets" stacking
// into a mess — while clips *within* one burst are intentionally staggered
// (not awaited individually) so they layer like an actual crowd murmur.
let burstQueue: Promise<void> = Promise.resolve();

async function runBurst(minCount: number, maxCount: number): Promise<void> {
  const count = randomInt(minCount, maxCount);
  const chosen = pickRandomDistinct(SFX_FILES, count);
  const finishes: Promise<void>[] = [];
  for (let i = 0; i < chosen.length; i++) {
    if (i > 0) await delay(randomInt(GAP_MIN_MS, GAP_MAX_MS));
    finishes.push(playOne(chosen[i]));
  }
  await Promise.all(finishes);
}

function playZawaBurst(minCount: number, maxCount: number): void {
  burstQueue = burstQueue.then(() => runBurst(minCount, maxCount));
}

/** RPS: called whenever the local player loses a star. Fewer stars left
 * (i.e. closer to elimination) means a bigger crowd reaction. */
export function playRPSStarLossSfx(starsRemaining: number): void {
  if (starsRemaining <= 1) playZawaBurst(3, 4);
  else if (starsRemaining === 2) playZawaBurst(2, 3);
  else playZawaBurst(1, 2);
}

/** E-card: called whenever the local player plays their Emperor/Slave
 * special card (not on citizen, and not on the round-4 auto-resolve, since
 * that isn't the client actually placing a card). */
export function playECardSpecialCardSfx(): void {
  playZawaBurst(1, 2);
}

/** E-card: called when a match concludes, from the local player's POV. */
export function playECardMatchEndSfx(won: boolean): void {
  if (won) playZawaBurst(1, 1);
  else playZawaBurst(2, 3);
}
