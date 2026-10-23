#!/usr/bin/env python3
"""Write a CA bundle without the eMudhra / emSign roots (security alert 2026-10-23: weak-key root CA; a network attacker could forge certificates, e.g. for a pip index).

  python3 scripts/make_ca_bundle_no_emsign.py [OUT]     # default OUT = ~/.config/security/ca-bundle-no-emsign.pem
Source: the system bundle /etc/ssl/certs/ca-certificates.crt.  Use it per tool: SSL_CERT_FILE, REQUESTS_CA_BUNDLE, PIP_CERT, CURL_CA_BUNDLE, GIT_SSL_CAINFO.  System-wide (needs root, once):
  sudo sed -i 's#^mozilla/emSign#!mozilla/emSign#' /etc/ca-certificates.conf && sudo update-ca-certificates --fresh
"""
import re
import subprocess
import sys
from pathlib import Path

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / '.config/security/ca-bundle-no-emsign.pem'
src = Path('/etc/ssl/certs/ca-certificates.crt').read_text()
certs = re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----\n?', src, re.S)
keep, drop = [], []
for c in certs:
    subj = subprocess.run(['openssl', 'x509', '-noout', '-subject'], input=c, capture_output=True, text=True).stdout.strip()
    (drop if re.search(r'emsign|emudhra', subj, re.I) else keep).append((c, subj))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(''.join(c if c.endswith('\n') else c + '\n' for c, _ in keep))
print(f'{len(certs)} certificates, {len(keep)} kept, {len(drop)} dropped:')
for _, s in drop:
    print('  ', s)
