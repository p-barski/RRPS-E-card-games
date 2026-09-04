// .card-chip's rendered width (see App.css).
const CHIP_WIDTH = 72;
// Cap the whole fan's footprint so a full hand (up to 12 cards) still fits on one row.
const FAN_MAX_WIDTH = 320;
// Never space chips out further than this even when there's plenty of room.
const MAX_GAP = 10;

// Returns the negative (overlapping) or small positive margin to put between
// consecutive card chips so that `total` of them always fit within
// FAN_MAX_WIDTH on a single row, however many there are.
export function fanChipMarginLeft(index: number, total: number): number | undefined {
  if (index === 0 || total <= 1) return undefined;
  return Math.min(MAX_GAP, (FAN_MAX_WIDTH - CHIP_WIDTH) / (total - 1) - CHIP_WIDTH);
}
