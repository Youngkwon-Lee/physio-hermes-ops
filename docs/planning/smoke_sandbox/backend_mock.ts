export function normalizeScore(x: number) {
  return Math.max(0, Math.min(100, x))
}
