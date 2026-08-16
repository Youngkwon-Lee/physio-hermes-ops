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

const [jsonPath, markdownPath] = process.argv.slice(2);
const report = JSON.parse(readFileSync(jsonPath, 'utf8'));
const totalOk = Object.values(report.summary || {}).reduce((sum, counts) => sum + Number(counts.ok || 0), 0);

if (totalOk <= 0) {
  process.exit(0);
}

const lines = [
  '재활 SNS 신호 수집',
  '',
  `generated_at: ${report.generated_at}`,
  `artifact: ${markdownPath}`,
  '',
  '요약:',
];

for (const [platform, counts] of Object.entries(report.summary || {})) {
  lines.push(`- ${platform}: ok=${counts.ok}, skipped=${counts.skipped}, error=${counts.error}`);
}

const okResults = (report.results || []).filter((result) => result.status === 'ok').slice(0, 5);
if (okResults.length) {
  lines.push('', '샘플:');
  for (const result of okResults) {
    const body = String(result.stdout || '').replace(/\s+/g, ' ').trim();
    lines.push(`- ${result.platform}/${result.query}: ${body.slice(0, 220)}${body.length > 220 ? '...' : ''}`);
  }
}

console.log(lines.join('\n'));
NODE
