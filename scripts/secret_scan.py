#!/usr/bin/env python3
"""Pre-publication scan of the files git tracks (pure stdlib, read-only): secrets, personal data, large files, LFS.

  python3 scripts/secret_scan.py             # tracked files of the working tree; exit 1 on any finding of kind SECRET / PERSONAL / ENV / LFS
  python3 scripts/secret_scan.py --history   # also every blob in the history of all branches (slower; nice -n 19)
  python3 scripts/secret_scan.py --big-mb 5  # size limit for the LARGE warning (default 10 MB; GitHub refuses > 100 MB)

Findings never print the secret itself, only file, line number and kind.
  SECRET    a key / token pattern (AWS, GitHub, OpenAI/Anthropic-style sk-, Google AIza, Slack, Hugging Face hf_, private-key block,
            a quoted value assigned to api_key / secret / token / password)
  PERSONAL  an e-mail address (noreply / example / documentation addresses and the git noreply form are allowed)
  ENV       a tracked .env / private-key / credential file name
  LARGE     a tracked file above --big-mb (warning only: not a failure; the hard GitHub limit is 100 MB)
  LFS       a .gitattributes with filter=lfs (the course checks out the repository without LFS; large files would be pointers)
"""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_EXT = ('.png', '.jpg', '.jpeg', '.gif', '.pdf', '.mp4', '.wav', '.mp3', '.mcap', '.db3', '.zip', '.gz', '.ico', '.webp', '.ttf', '.otf', '.pt', '.safetensors')
SECRET_RX = [
    ('aws-access-key', re.compile(r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b')),
    ('github-token', re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b')),
    ('sk-token', re.compile(r'\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{24,}\b')),
    ('google-api-key', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
    ('slack-token', re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b|https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,}')),
    ('huggingface-token', re.compile(r'\bhf_[A-Za-z0-9]{30,}\b')),
    ('private-key', re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----')),
    ('bearer-token', re.compile(r'\bBearer\s+[A-Za-z0-9._~+/-]{30,}=*')),
    ('assigned-secret', re.compile(r'''(?i)\b(?:api[_-]?key|secret(?:[_-]?key)?|access[_-]?token|auth[_-]?token|password|passwd)\b["']?\s*[:=]\s*["'][A-Za-z0-9_\-+/=.]{16,}["']''')),
]
PLACEHOLDER_WORDS = re.compile(r'(?i)your|example|dummy|placeholder|changeme|xxxx|\.\.\.|<[^>]+>|\$\{|os\.environ|getenv')
EMAIL_RX = re.compile(r'(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b')
EMAIL_OK = re.compile(r'(?i)@(?:users\.noreply\.github\.com|noreply\.[a-z.]+|example\.(?:com|org|net)|localhost|anthropic\.com)$|^noreply@|^git@github\.com$')
BAD_NAMES = re.compile(r'(?i)(?:^|/)(?:\.env(?:\.[\w.-]+)?|id_(?:rsa|dsa|ecdsa|ed25519)|[^/]*\.(?:pem|p12|pfx|key)|credentials(?:\.json)?|\.netrc|\.npmrc|\.pypirc)$')
ENV_EXAMPLE = re.compile(r'(?i)\.(?:example|sample|template)$')


def scan_text(name: str, text: str) -> list[tuple[str, str, int]]:
    """[(kind, file, line)] for one text."""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if len(line) > 4000:        # minified / data line: still scan the patterns, which are anchored on word boundaries
            line = line[:4000]
        for kind, rx in SECRET_RX:
            m = rx.search(line)
            if m and not (kind in ('assigned-secret', 'bearer-token') and PLACEHOLDER_WORDS.search(m.group(0))):
                hits.append(('SECRET:' + kind, name, i))
        for m in EMAIL_RX.finditer(line):
            if not EMAIL_OK.search(m.group(0)):
                hits.append(('PERSONAL:email', name, i))
    return hits


def git(*args: str, cwd: Path = ROOT) -> bytes:
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, check=True).stdout


def scan_tracked(root: Path = ROOT, big_mb: float = 10.0):
    findings, warnings = [], []
    names = [n.decode() for n in git('ls-files', '-z', cwd=root).split(b'\0') if n]
    for n in names:
        p = root / n
        if BAD_NAMES.search(n) and not ENV_EXAMPLE.search(n):
            findings.append(('ENV:file-name', n, 0))
        if p.is_symlink() or not p.is_file():
            continue
        size = p.stat().st_size
        if size > big_mb * 1e6:
            warnings.append(('LARGE', n, round(size / 1e6, 1)))
        if n.endswith(SKIP_EXT) or size > 20e6:
            continue
        try:
            findings += scan_text(n, p.read_text(encoding='utf8'))
        except UnicodeDecodeError:
            continue
        if n.endswith('.gitattributes') and 'filter=lfs' in p.read_text(encoding='utf8'):
            findings.append(('LFS', n, 0))
    return names, findings, warnings


def scan_history(root: Path = ROOT):
    """Every distinct text blob of every ref (read via cat-file --batch; each blob scanned once)."""
    out = git('rev-list', '--objects', '--all', cwd=root).decode(errors='replace').splitlines()
    path_of = {}
    for ln in out:
        sha, _, path = ln.partition(' ')
        if path and not path.endswith(SKIP_EXT):
            path_of.setdefault(sha, path)
    findings = []
    proc = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for sha, path in path_of.items():
        proc.stdin.write(sha.encode() + b'\n')
        proc.stdin.flush()
        head = proc.stdout.readline().split()
        if len(head) < 3:
            continue
        size = int(head[2])
        body = proc.stdout.read(size)
        proc.stdout.read(1)
        if head[1] != b'blob' or size > 20e6:
            continue
        try:
            findings += [(k, f'{path}@{sha[:8]}', ln) for k, _, ln in scan_text(path, body.decode('utf8'))]
        except UnicodeDecodeError:
            pass
    proc.stdin.close()
    proc.wait()
    return len(path_of), findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--history', action='store_true')
    ap.add_argument('--big-mb', type=float, default=10.0)
    a = ap.parse_args(argv)
    names, findings, warnings = scan_tracked(ROOT, a.big_mb)
    print(f'tracked files scanned: {len(names)}')
    for k, f, ln in findings:
        print(f'FINDING {k}: {f}' + (f':{ln}' if ln else ''))
    for k, f, v in warnings:
        print(f'WARNING {k}: {f} ({v} MB)')
    if a.history:
        n, hf = scan_history(ROOT)
        print(f'history blobs scanned: {n}')
        for k, f, ln in hf:
            print(f'FINDING(history) {k}: {f}:{ln}')
        findings += hf
    top = sorted(((ROOT / n).stat().st_size, n) for n in names if (ROOT / n).is_file())[-3:]
    print('largest tracked files: ' + ', '.join(f'{n} {s / 1e6:.1f} MB' for s, n in reversed(top)))
    print(f'RESULT: {len(findings)} finding(s), {len(warnings)} warning(s)')
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
