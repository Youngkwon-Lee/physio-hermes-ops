export type ScoreIssue = 'missing' | 'not-finite' | 'below-range' | 'above-range' | null

export interface NormalizedScoreMeta {
  raw: unknown
  sanitized: number
  normalized: number
  issue: ScoreIssue
  isClamped: boolean
}

function clampScore(value: number) {
  return Math.max(0, Math.min(100, value))
}

export function normalizeScore(x: number) {
  const sanitized = Number.isFinite(x) ? Math.round(x) : 0
  return clampScore(sanitized)
}

export function normalizeScoreWithMeta(input: unknown): NormalizedScoreMeta {
  if (input == null || input === '') {
    return {
      raw: input,
      sanitized: 0,
      normalized: 0,
      issue: 'missing',
      isClamped: false,
    }
  }

  const numeric = typeof input === 'number' ? input : Number(input)

  if (!Number.isFinite(numeric)) {
    return {
      raw: input,
      sanitized: 0,
      normalized: 0,
      issue: 'not-finite',
      isClamped: false,
    }
  }

  const sanitized = Math.round(numeric)
  const normalized = clampScore(sanitized)
  const issue = sanitized < 0 ? 'below-range' : sanitized > 100 ? 'above-range' : null

  return {
    raw: input,
    sanitized,
    normalized,
    issue,
    isClamped: normalized !== sanitized,
  }
}
