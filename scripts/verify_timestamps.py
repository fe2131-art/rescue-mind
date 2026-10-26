#!/usr/bin/env python3
"""Verify the OpenTimestamps proofs of docs/timestamps/ without a local Bitcoin node (docs/PROVENANCE.md).

For every `X.txt.ots`: (1) the digest inside the proof equals the SHA-256 of `X.txt`; (2) for every Bitcoin attestation, the commitment obtained by replaying
the proof's operations equals the Merkle root of that Bitcoin block, read from a public block explorer (blockstream.info).  The explorer is a trust
assumption; for a node-independent check use `ots verify` with your own Bitcoin node.  Proofs attest the BYTES of the `.txt` files (which quote the
commit hashes of the original history); they do not attest the hashes of the rewritten `main`.

  pip install opentimestamps            # python-opentimestamps
  python3 scripts/verify_timestamps.py [docs/timestamps]
"""
from __future__ import annotations
import datetime
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

try:
    from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
    from opentimestamps.core.serialize import BytesDeserializationContext
    from opentimestamps.core.timestamp import DetachedTimestampFile
except ImportError:
    sys.exit('pip install opentimestamps  (python-opentimestamps) is required')

ROOT = Path(__file__).resolve().parents[1]
API = 'https://blockstream.info/api'
_cache: dict = {}


def block(height):
    if height not in _cache:
        h = urllib.request.urlopen(f'{API}/block-height/{height}', timeout=30).read().decode().strip()
        j = json.loads(urllib.request.urlopen(f'{API}/block/{h}', timeout=30).read())
        _cache[height] = (j['merkle_root'], j['timestamp'])
    return _cache[height]


def main():
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'docs/timestamps'
    files = sorted(d.glob('*.ots'))
    ok = att_total = bad = 0
    for ots in files:
        txt = d / ots.name[:-4]
        dt = DetachedTimestampFile.deserialize(BytesDeserializationContext(ots.read_bytes()))
        if dt.file_digest != hashlib.sha256(txt.read_bytes()).digest():
            print(f'FAIL {ots.name}: the digest in the proof is not the SHA-256 of {txt.name}')
            bad += 1
            continue
        res = []
        for msg, att in dt.timestamp.all_attestations():
            if isinstance(att, BitcoinBlockHeaderAttestation):
                root, ts = block(att.height)
                res.append((att.height, msg[::-1].hex() == root, ts))
        good = [r for r in res if r[1]]
        att_total += len(res)
        bad += sum(not r[1] for r in res)
        if good and all(r[1] for r in res):
            ok += 1
            first = min(good)
            when = datetime.datetime.fromtimestamp(first[2], datetime.timezone.utc).strftime('%Y-%m-%d %H:%MZ')
            print(f'ok   {txt.name:42s} {len(res)} Bitcoin attestation(s); earliest block {first[0]} ({when})')
        else:
            print(f'FAIL {ots.name}: {"no Bitcoin attestation" if not res else "a Merkle root does not match"}')
            bad += not res
    print(f'{ok}/{len(files)} proofs verified; {att_total} Bitcoin attestations checked; {bad} problem(s)')
    sys.exit(1 if bad or ok != len(files) else 0)


if __name__ == '__main__':
    main()
