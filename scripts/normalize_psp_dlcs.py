#!/usr/bin/env python3
"""
normalize_psp_dlcs.py

Reads PSP_DLCS.tsv from the repo, normalizes headers to snake_case, detects truncated fields,
and writes:
 - PSP_DLCS_clean.ndjson : NDJSON of normalized rows
 - PSP_DLCS_report.txt   : simple validation report
 - PSP_DLCS_normalized_sample.tsv : header + non-truncated sample rows (if any)

Usage: python3 normalize_psp_dlcs.py

"""
import csv
import json
import re
from pathlib import Path

IN = Path('PSP_DLCS.tsv')
OUT_NDJSON = Path('PSP_DLCS_clean.ndjson')
OUT_REPORT = Path('PSP_DLCS_report.txt')
OUT_SAMPLE = Path('PSP_DLCS_normalized_sample.tsv')

TRUNC_PATTERN = re.compile(r"(\[\.\.\.\]|\.{3})$")

def normalize_col(c):
    c = (c or '').strip()
    c = c.replace('.', '')
    c = c.replace('®', '')
    c = c.replace('™', '')
    c = re.sub(r'\s+', '_', c)
    c = c.lower()
    return c

def parse_size(s):
    if s is None or s == '':
        return None
    s = s.replace(',', '').strip()
    if s.isdigit():
        return int(s)
    return None

def is_truncated(s):
    if s is None:
        return False
    return bool(TRUNC_PATTERN.search(s))

if not IN.exists():
    print('PSP_DLCS.tsv not found in repo root. Please run from repository root.')
    raise SystemExit(1)

with IN.open('r', encoding='utf-8', errors='replace') as fh:
    first = fh.readline()
    m = re.match(r'^\s*\d+\|\s+(.*)', first)
    if m:
        header_line = m.group(1)
    else:
        header_line = first
    rest = fh.read().splitlines()

lines = [header_line] + rest
reader = csv.reader(lines, delimiter='\t')
rows = list(reader)
if not rows:
    print('No rows parsed')
    raise SystemExit(1)

raw_header = rows[0]
normalized_header = [normalize_col(h) for h in raw_header]

records = []
truncated_rows = []

for i, row in enumerate(rows[1:], start=2):
    if len(row) < len(normalized_header):
        row += [''] * (len(normalized_header) - len(row))
    record = {k: v for k, v in zip(normalized_header, row)}
    if 'file_size' in record and record.get('file_size'):
        sz = parse_size(record['file_size'])
        if sz is not None:
            record['file_size_bytes'] = sz
    truncated_fields = [k for k, v in record.items() if isinstance(v, str) and is_truncated(v)]
    if truncated_fields:
        truncated_rows.append({'line': i, 'title_id': record.get('title_id'), 'truncated_fields': truncated_fields})
    records.append(record)

with OUT_NDJSON.open('w', encoding='utf-8') as out:
    for rec in records:
        out.write(json.dumps(rec, ensure_ascii=False) + '\n')

with OUT_REPORT.open('w', encoding='utf-8') as rep:
    rep.write('Total rows: %d\n' % len(records))
    rep.write('Header mapping (raw -> normalized):\n')
    for raw, norm in zip(raw_header, normalized_header):
        rep.write(f'  "{raw}" -> "{norm}"\n')
    rep.write('\nTruncated rows detected: %d\n' % len(truncated_rows))
    for t in truncated_rows[:200]:
        rep.write('  line %d title_id=%s truncated=%s\n' % (t['line'], t.get('title_id'), ','.join(t['truncated_fields'])))
    if len(truncated_rows) > 200:
        rep.write('  ... (more)\n')

sample_rows = [r for r in records if not any(is_truncated(v) for v in r.values())]
with OUT_SAMPLE.open('w', encoding='utf-8') as s:
    s.write('\t'.join(normalized_header) + '\n')
    for rec in sample_rows[:100]:
        s.write('\t'.join(rec.get(h, '') for h in normalized_header) + '\n')

print('Wrote:', OUT_NDJSON, OUT_REPORT, OUT_SAMPLE)
print('Detected truncated rows:', len(truncated_rows))
print('Done')
