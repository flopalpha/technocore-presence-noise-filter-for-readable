'''Technocore presence noise filter for readable review.

Reads public room text supplied by the user and labels
repetitive presence lines versus substantive posts.
Local read-only analysis only.
'''

import hashlib
import json
import re
from collections import defaultdict

DID_PATTERN = re.compile(r'did:key:z[1-9A-HJ-NP-Za-km-z]+')
JSON_SNIPPET = re.compile(r'[{][^{}]*:[^{}]*[}]')

CONTINUITY_WORDS = [
    'continuity',
    'check-in',
    'checkin',
    'request id',
    'request-id',
    'did:key',
]

TELEMETRY_WORDS = [
    'telemetry',
    'uptime',
    'ram',
    'load average',
    'load avg',
    'cpu',
    'memory',
]

TUNING_WORDS = [
    'long-poll',
    'longpoll',
    'long poll',
    'cursor',
    'read load',
    'tuning',
    'wait 10',
    'poll wait',
]

PRESENCE_PHRASES = [
    'heartbeat',
    'presence',
    'layer online',
    'still online',
    'signed presence',
    'ed25519 verification',
    'verification heartbeat',
    'i am online',
    'node online',
    'agent online',
]

def normalize_text(text):
    if text is None:
        return ''
    s = str(text).lower().strip()
    s = ' '.join(s.split())
    s = re.sub(r'[^a-z0-9 ]', '', s)
    s = ' '.join(s.split())
    return s

def text_hash(normalized):
    data = str(normalized).encode('utf-8')
    return hashlib.sha256(data).hexdigest()[:16]

def is_json_payload(text):
    if not text:
        return False
    s = str(text)
    if '{' not in s or '}' not in s or ':' not in s:
        return False
    return bool(JSON_SNIPPET.search(s))

def did_is_valid(value):
    prefix = 'did:key:z'
    if not value.startswith(prefix):
        return False
    tail = value[len(prefix):]
    if len(tail) < 20 or len(tail) > 100:
        return False
    bad = set('0OIl')
    for ch in tail:
        if ch in bad:
            return False
    return True

def find_dids(text):
    if not text:
        return []
    out = []
    for m in DID_PATTERN.finditer(str(text)):
        val = m.group(0)
        out.append({'value': val, 'valid': did_is_valid(val)})
    return out

def classify_post(text):
    s = str(text) if text is not None else ''
    low = s.lower()
    has_json = is_json_payload(s)
    dids = find_dids(s)
    has_cont = False
    for w in CONTINUITY_WORDS:
        if w in low:
            has_cont = True
            break
    has_telem = False
    for w in TELEMETRY_WORDS:
        if w in low:
            has_telem = True
            break
    has_tune = False
    for w in TUNING_WORDS:
        if w in low:
            has_tune = True
            break
    reasons = []
    if has_json:
        reasons.append('has json-like payload')
    if has_cont:
        reasons.append('continuity terms')
    if has_telem:
        reasons.append('telemetry terms')
    if has_tune:
        reasons.append('tuning terms')
    for ph in PRESENCE_PHRASES:
        if ph in low:
            reasons.append('presence phrase: ' + ph)
            break
    label = 'other'
    category = 'other'
    if has_cont:
        label = 'substantive'
        category = 'continuity'
    elif has_telem:
        label = 'substantive'
        category = 'telemetry'
    elif has_tune:
        label = 'substantive'
        category = 'tuning_tip'
    elif has_json:
        label = 'substantive'
        category = 'general'
    else:
        found = False
        for ph in PRESENCE_PHRASES:
            if ph in low:
                found = True
                break
        if found and len(s) < 300:
            label = 'presence_noise'
            category = 'presence'
    return {
        'label': label,
        'category': category,
        'reasons': reasons,
        'has_json': has_json,
        'dids': dids,
    }

def parse_log_lines(lines, default_room='technocore'):
    posts = []
    n = 0
    for raw in lines:
        n += 1
        if raw is None:
            continue
        line = str(raw).strip()
        if line == '':
            continue
        if line.startswith('{'):
            try:
                obj = json.loads(line)
            except ValueError:
                obj = None
            if isinstance(obj, dict):
                seq = obj.get('seq', obj.get('id', n))
                room = obj.get('room', obj.get('channel', default_room))
                txt = obj.get('text', obj.get('message', obj.get('body', '')))
                posts.append({
                    'seq': seq,
                    'room': str(room),
                    'text': str(txt),
                })
                continue
        if '|' in line:
            parts = line.split('|', 2)
            if len(parts) == 3 and parts[0].strip().isdigit():
                posts.append({
                    'seq': int(parts[0].strip()),
                    'room': parts[1].strip() or default_room,
                    'text': parts[2].strip(),
                })
                continue
            if len(parts) == 2 and parts[0].strip().isdigit():
                posts.append({
                    'seq': int(parts[0].strip()),
                    'room': default_room,
                    'text': parts[1].strip(),
                })
                continue
        posts.append({'seq': n, 'room': default_room, 'text': line})
    return posts

def parse_log_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    return parse_log_lines(lines)

def classify_all(posts):
    out = []
    for p in posts:
        r = classify_post(p.get('text', ''))
        q = dict(p)
        q.update(r)
        out.append(q)
    return out

def cluster_posts(posts):
    groups = defaultdict(list)
    norms = {}
    for p in posts:
        norm = normalize_text(p.get('text', ''))
        h = text_hash(norm)
        groups[h].append(p)
        norms[h] = norm
    clusters = []
    for h, items in groups.items():
        seqs = []
        for x in items:
            seqs.append(x.get('seq'))
        clusters.append({
            'hash': h,
            'normalized': norms[h],
            'count': len(items),
            'seqs': seqs,
            'example': items[0].get('text', ''),
        })
    clusters.sort(key=lambda c: c['count'], reverse=True)
    return clusters

def surface_substantive(classified):
    out = []
    for p in classified:
        if p.get('label') == 'substantive':
            out.append(p)
    return out

def summarize(classified, clusters):
    total = len(classified)
    noise = 0
    signal = 0
    for p in classified:
        if p.get('label') == 'presence_noise':
            noise += 1
        elif p.get('label') == 'substantive':
            signal += 1
    other = total - noise - signal
    dup_groups = []
    for c in clusters:
        if c.get('count', 0) > 1:
            dup_groups.append(c)
    dup_lines = 0
    for c in dup_groups:
        dup_lines += c.get('count', 0)
    ratio = 0.0
    if total > 0:
        ratio = signal / total
    return {
        'total': total,
        'noise': noise,
        'signal': signal,
        'other': other,
        'signal_ratio': round(ratio, 3),
        'cluster_count': len(clusters),
        'dup_group_count': len(dup_groups),
        'dup_line_count': dup_lines,
    }

def write_markdown_summary(summary, substantive, clusters, out_path):
    lines = []
    lines.append('# Technocore Readable Review')
    lines.append('')
    lines.append('Local review of public room text. No posts were sent.')
    lines.append('')
    lines.append('## Signal summary')
    lines.append('')
    lines.append('- Total posts: ' + str(summary.get('total', 0)))
    lines.append('- Presence noise: ' + str(summary.get('noise', 0)))
    lines.append('- Substantive: ' + str(summary.get('signal', 0)))
    lines.append('- Other: ' + str(summary.get('other', 0)))
    lines.append('- Signal ratio: ' + str(summary.get('signal_ratio', 0)))
    lines.append('- Clusters: ' + str(summary.get('cluster_count', 0)))
    lines.append('- Duplicate groups: ' + str(summary.get('dup_group_count', 0)))
    lines.append('- Lines in duplicate groups: ' + str(summary.get('dup_line_count', 0)))
    lines.append('')
    lines.append('## Substantive posts')
    lines.append('')
    if not substantive:
        lines.append('None found.')
    else:
        for p in substantive:
            seq = p.get('seq', '?')
            room = p.get('room', '?')
            cat = p.get('category', '?')
            txt = str(p.get('text', ''))[:280]
            txt = txt.replace(chr(10), ' ')
            lines.append('- seq ' + str(seq) + ' [' + str(room) + '] (' + str(cat) + '): ' + txt)
    lines.append('')
    lines.append('## Repeated presence groups')
    lines.append('')
    shown = 0
    for c in clusters:
        if c.get('count', 0) < 2:
            continue
        if shown >= 10:
            break
        seqs = c.get('seqs', [])
        small = seqs[:8]
        parts = []
        for s in small:
            parts.append(str(s))
        seq_str = ', '.join(parts)
        ex = str(c.get('example', ''))[:200]
        ex = ex.replace(chr(10), ' ')
        lines.append('- x' + str(c.get('count')) + ' seqs [' + seq_str + ']: ' + ex)
        shown += 1
    if shown == 0:
        lines.append('No repeats.')
    lines.append('')
    lines.append('## Audit')
    lines.append('')
    lines.append('Check seq references above against the source log.')
    lines.append('')
    text = chr(10).join(lines)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return out_path
