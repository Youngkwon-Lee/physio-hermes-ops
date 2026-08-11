#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

REPO_DIR="${KINELO_OPS_DIR:-$HOME/kinelo-ops}"
OUT_DIR="${REHAB_SNS_OUTPUT_DIR:-$HOME/.hermes/rehab-sns}"
STAMP="$(date +%F)"
JSON_OUT="$OUT_DIR/rehab-sns-signals-$STAMP.json"
MD_OUT="$OUT_DIR/rehab-sns-signals-$STAMP.md"

mkdir -p "$OUT_DIR"
cd "$REPO_DIR"

node scripts/collect-rehab-sns-signals.mjs \
  --queries "${REHAB_SNS_QUERIES:-rehabilitation AI,rehabilitation robotics,AI physical therapy,telerehabilitation,exoskeleton rehab,gait analysis,movement assessment}" \
  --platforms "${REHAB_SNS_PLATFORMS:-twitter,reddit,facebook,instagram,linkedin}" \
  --limit "${REHAB_SNS_LIMIT:-3}" \
  --output-json "$JSON_OUT" \
  --output-markdown "$MD_OUT" \
  --no-post >/dev/null

node --input-type=module - "$JSON_OUT" "$MD_OUT" <<'NODE'
import { readFileSync } from 'node:fs';
import { filterRelevantSnsResults } from './scripts/lib/agent-reach-sns-collector.mjs';

const [jsonPath, markdownPath] = process.argv.slice(2);
const report = JSON.parse(readFileSync(jsonPath, 'utf8'));
const totalOk = Object.values(report.summary || {}).reduce((sum, counts) => sum + Number(counts.ok || 0), 0);
const relevantResults = filterRelevantSnsResults(report.results || [], {
  minScore: Number.parseInt(process.env.REHAB_SNS_MIN_RELEVANCE || '2', 10),
});

if (totalOk <= 0) {
  const failed = (report.results || [])
    .filter((result) => result.status === 'error' || result.status === 'skipped')
    .slice(0, 3)
    .map((result) => `${result.platform}/${result.query}: ${result.reason || result.stderr || 'backend unavailable'}`);
  console.log([
    '재활 SNS 수집: 확인 필요',
    `ok=0 / 오류·건너뜀=${failed.length || '확인 불가'}`,
    ...failed.map((reason) => `- ${reason}`),
  ].join('\n'));
  process.exit(0);
}

if (relevantResults.length === 0) {
  console.log(`재활 SNS 수집: 관련 신호 0건 (수집 성공 ${totalOk}건, 관련성 필터 통과 0건)`);
  process.exit(0);
}

const lines = [
  '재활 SNS 신호 수집',
  '',
  `generated_at: ${report.generated_at}`,
  `artifact: ${markdownPath}`,
  `relevant: ${relevantResults.length} / ok: ${totalOk}`,
  '',
  '요약:',
];

for (const [platform, counts] of Object.entries(report.summary || {})) {
  lines.push(`- ${platform}: ok=${counts.ok}, skipped=${counts.skipped}, error=${counts.error}`);
}

const okResults = relevantResults.slice(0, 5);
if (okResults.length) {
  lines.push('', '샘플:');
  for (const result of okResults) {
    const body = String(result.stdout || '').replace(/\s+/g, ' ').trim();
    lines.push(`- ${result.platform}/${result.query} [score ${result.relevance.score}]: ${body.slice(0, 220)}${body.length > 220 ? '...' : ''}`);
  }
}

console.log(lines.join('\n'));
NODE
