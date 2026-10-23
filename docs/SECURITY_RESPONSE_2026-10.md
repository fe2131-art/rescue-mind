# Security response, 2026-10-23 (supply-chain alerts: weak-key CA, Node.js releases)

**Alerts.** (1) The eMudhra / emSign root CAs signed with very weak keys, so a network attacker could forge certificates (for example for a pip index); pip bundles its own CA list, so the system update alone is not enough; fixed releases: pip 26.2.2, uv 0.13.4. (2) Node.js security releases of 2026-10-21: 22.23.4, 24.22.1, 26.12.1.
**What the repository's environment did** (no personal data here; host-wide steps that need root are listed for the administrator):
| item | before | after |
|---|---|---|
| pip (host user, project venvs, container system and `/opt/rescuemind-venv`) | 22.0.2 to 26.1.2 / 24.0 / 25.3 | 26.2.2 |
| uv | 0.10.6 | 0.13.5 |
| Node.js (nvm default) | 24.12.0 | 24.22.1 |
| emSign / eMudhra roots in the containers `rm-dev`, `rm-next`, `rm-voicevox` | trusted | removed (`/etc/ca-certificates.conf`, `update-ca-certificates --fresh`); ca-certificates 20260816 |
| host tools of the user (pip, requests, curl, git, Python ssl) | system store | a bundle without emSign: `scripts/make_ca_bundle_no_emsign.py`, set through `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `PIP_CERT`, `CURL_CA_BUNDLE`, `GIT_SSL_CAINFO` |
| `docker/Dockerfile`, `docker/latex/Dockerfile`, `scripts/install_local_vlm_v100.sh` | pip pinned below 26, no distrust | pip >= 26.2.2, emSign distrusted, pip uses the system bundle |
**Needs root on the host (not done by the assistant):** `sudo sed -i 's#^mozilla/emSign#!mozilla/emSign#' /etc/ca-certificates.conf && sudo update-ca-certificates --fresh`; the system `pip` (apt) stays old (`python3 -m pip` of the user now resolves to the user's pip 26.2.2); reboot into the installed newer kernel; NVIDIA 570 security updates.
**Not changed:** Node.js runs bundled inside editor servers (cannot be updated by the user); the `uv` virtualenvs have no pip of their own (uv is updated).
