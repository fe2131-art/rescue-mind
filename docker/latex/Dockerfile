# Paper build environment (no host TeX needed):  docker build -t rescuemind:latex docker/latex
FROM texlive/texlive:latest-medium
# Security (2026-10-23): emSign roots distrusted in the CA store
RUN sed -i 's#^mozilla/emSign#!mozilla/emSign#' /etc/ca-certificates.conf && update-ca-certificates --fresh
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/* \
 && tlmgr update --self \
 && (tlmgr install ieeetran cleveref xurl multirow makecell threeparttable enumitem caption subfig microtype preprint cite || true) \
 && kpsewhich IEEEtran.cls IEEEtran.bst cleveref.sty balance.sty
