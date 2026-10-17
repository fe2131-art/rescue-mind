# new_refs.bib verification notes (checked 2026-10-17)

Method: arXiv abstract pages (title/authors/comments); venue, DOI, pages via publisher/proceedings pages (PMLR, NeurIPS proceedings, MIT DSpace) or OpenAlex DOI records (IEEE Xplore pages returned empty to the fetcher).
Raw author lists were checked against arXiv/proceedings. Lists >10 authors: ConceptGraphs kept full (16, as requested); Hofer truncated (15, first 6 + others).

## 1. Memory / changing environments
- anwar2025remembr — long-horizon spatio-temporal robot memory; ICRA 2025 pp.2838-2845 — https://arxiv.org/abs/2409.13682 ; https://api.openalex.org/works/doi:10.1109/ICRA55743.2025.11127706
- xie2024embodiedrag — graph-structured embodied memory for retrieval (arXiv only, no venue found) — https://arxiv.org/abs/2409.18313
- gu2024conceptgraphs — open-vocabulary 3D scene graph map for planning; ICRA 2024 pp.5021-5028 — https://arxiv.org/abs/2309.16650 ; OpenAlex doi 10.1109/ICRA57147.2024.10610243
- werby2024hovsg — hierarchical scene-graph memory for language navigation; RSS 2024 — https://arxiv.org/abs/2403.17846 ; OpenAlex doi 10.15607/RSS.2024.XX.077
- rana2023sayplan — LLM planning over scene-graph memory; CoRL 2023 (PMLR 229:23-72) — https://proceedings.mlr.press/v229/rana23a.html ; https://arxiv.org/abs/2307.06135
- wang2025karma — long/short-term memory for embodied agents; ICRA 2025 — https://arxiv.org/abs/2409.14908 ; OpenAlex doi 10.1109/ICRA55743.2025.11128047 (title match; authors from arXiv)
- barmann2025hemv — hierarchical episodic memory verbalization over life-long robot experience; Humanoids 2025 pp.783-790 — https://arxiv.org/abs/2409.17702 ; OpenAlex doi 10.1109/Humanoids65713.2025.11203101
- hughes2022hydra — real-time 3D scene graph building (spatial perception baseline); RSS 2022 — https://arxiv.org/abs/2201.13360 ; OpenAlex doi 10.15607/RSS.2022.XVIII.050
- schmid2024khronos — spatio-temporal SLAM detecting scene changes over time; RSS 2024 — https://arxiv.org/abs/2402.13817 ; OpenAlex doi 10.15607/RSS.2024.XX.081
- behrens2025lostfound — tracking object changes in dynamic scene graphs; RA-L 10(4):3739-3746 — https://arxiv.org/abs/2411.19162 ; OpenAlex doi 10.1109/LRA.2025.3544518
- sun2026memorylies — stale spatial memory degrades VLM agents (core motivation for remembered-supply failure) — https://arxiv.org/abs/2608.04574 (arXiv preprint, no venue)
- yin2026glove — verifying LLM memory against environment to realign stale memory — https://arxiv.org/abs/2601.19249 (arXiv preprint; v2 dated 2026-09-26)
- tang2026vlmdewm — external verifiable world model for resilient VLM planning — https://arxiv.org/abs/2602.15549 (arXiv preprint)
- biber2005dynamic — classic long-term mapping in changing environments; RSS I pp.17-24 — OpenAlex doi 10.15607/RSS.2005.I.003
- krajnik2017fremen — long-term autonomy by modelling environmental change over time; T-RO 33(4):964-977 — OpenAlex doi 10.1109/TRO.2017.2665664

## 2. Active perception
- bajcsy1988active — foundational active-perception definition; Proc. IEEE 76(8):966-1005 — OpenAlex doi 10.1109/5.5968
- bajcsy2018revisiting — modern restatement of active perception; Autonomous Robots 42(2):177-196 — OpenAlex doi 10.1007/s10514-017-9615-3
- ren2024exploreuntil — VLM confidence-driven exploration, calibrated stopping; RSS 2024 — https://arxiv.org/abs/2403.15941 ; OpenAlex doi 10.15607/RSS.2024.XX.089
- scott2003viewplanning — classic view-planning / next-best-view survey; ACM CSUR 35(1):64-96 — OpenAlex doi 10.1145/641865.641868
- sripada2024sceneexploration — VLM-driven scene exploration for active perception (arXiv only) — https://arxiv.org/abs/2409.17641

## 3. Robustness / sim-to-real
- hendrycks2019benchmarking — ImageNet-C corruption benchmark (ICLR 2019, per arXiv comment "ICLR 2019 camera-ready") — https://arxiv.org/abs/1903.12261
- michaelis2019benchmarking — corruption benchmark for object detection (arXiv only) — https://arxiv.org/abs/1907.07484
- chen2023benchmarking — multimodal corruption benchmark for pre-trained VLMs; NeurIPS 2023 D&B (vol 36) — https://proceedings.neurips.cc/paper_files/paper/2023/hash/a2a544e43acb8b954dc5846ff0d77ad5-Abstract.html
- schiappa2022robustness — video-language models degrade under visual perturbations; NeurIPS 2022 D&B (vol 35) — https://proceedings.neurips.cc/paper_files/paper/2022/hash/de6ff07cbd222c10d694c2b2f732aceb-Abstract.html ; https://arxiv.org/abs/2207.02159
- hofer2021sim2real — sim-to-real gap survey/editorial; T-ASE 18(2):398-400 — https://dspace.mit.edu/handle/1721.1/138850?show=full ; https://www.ias.informatik.tu-darmstadt.de/Publications/BibTex?id=11417. Author order follows MIT record (first 6 shown); arXiv 2012.03806 (workshop-summary title, 15 authors) swaps Mozifian/Golemo.

## 4. Diverse redundancy
- avizienis1985nversion — N-version programming for design-fault tolerance; TSE SE-11(12):1491-1501 — OpenAlex doi 10.1109/TSE.1985.231893 (author listed as "A. Avizienis")
- knight1986experimental — independent versions still fail together; TSE SE-12(1):96-109 — OpenAlex doi 10.1109/TSE.1986.6312924
- du2024debate — multiple LLM instances debating improves factuality; ICML 2024 (PMLR 235:11733-11763) — https://proceedings.mlr.press/v235/du24e.html ; https://arxiv.org/abs/2305.14325

## 5. Run-time safety
- sinha2024realtime — fast LLM anomaly detection plus reactive safe fallback; RSS 2024 — https://arxiv.org/abs/2407.08735 ; OpenAlex doi 10.15607/RSS.2024.XX.114
- yuan2026whentoact — uncertainty-aware policy steering: act, ask or learn — https://arxiv.org/abs/2602.22474 (v2 comment: "To appear in RSS 2026"; proceedings page not checked, hence the note field)

## 6. Cloudflare Clef
- chen2026clefblog — primary source for Clef/Clef-flash decision models (Cloudflare Blog, 2026-10-01, author Michelle Chen) — https://blog.cloudflare.com/clef-decision-models
- cloudflare2026clefchangelog — Workers AI release notice: Clef 27B, Clef-flash 9B, Apache 2.0 (2026-10-01) — https://developers.cloudflare.com/changelog/post/2026-10-01-clef-workers-ai/
- gihyo2026clef — Japanese news coverage of Clef release (2026-10-02, no author listed) — https://gihyo.jp/article/2026/10/cloudflare-clef-decision-model
  Original title: Cloudflare、オープンソースのマルチモーダル意思決定モデル「Clef」と「Clef-flash」をリリース (the .bib uses a bracketed English gloss to stay ASCII/pdfLaTeX-safe).

## Caveats / not independently verified
- Blog and changelog differ on base model: blog says Clef = Qwen3.8-27B, Clef-flash = Qwen3.5-9B; changelog names none. Cite the blog for base models.
- Embodied-RAG, Sun&Zhang, GLOVE, VLM-DEWM, Sripada, Michaelis: arXiv-only (no venue listed anywhere found); kept as @misc preprints.
- No entries were dropped for failing verification. Page numbers left out where not verified (RSS, KARMA, Chen/Schiappa NeurIPS).
- Wrong guess corrected: arXiv 2107.00222 is not Hofer; Hofer is DOI 10.1109/TASE.2021.3064065.

## 7. Related-work additions (checked 2026-10-17)
Method: arXiv abstract pages via curl; DOI/pages via Crossref API; venue via proceedings pages. IEEE Xplore pages were not fetched. Where no venue could be confirmed the entry is an arXiv preprint.
- oloo2026vaptamp (VAP-TAMP) — arXiv 2604.26988 v1, 2026-04-28, cs.RO, 12 authors, no venue. Full text read from the arXiv HTML version (not only the abstract): Alg. 2 and Sec. IV-B give paraphrased yes/no questions, majority vote, a view-sufficiency query and a VLM-suggested viewing direction with a viewpoint budget; failed verification corrects the scene graph and triggers PDDL replanning; 100 real trials plus OmniGibson with injected failures.
- angelopoulos2024conformalrisk — Conformal Risk Control; arXiv 2208.02814; ICLR 2024 proceedings page.
- angelopoulos2025ltt — Learn then Test; Crossref 10.1214/24-AOAS1998 (Ann. Appl. Stat. 19(2):1641-1662); arXiv 2110.01052.
- lekeufack2024conformaldecision — Conformal Decision Theory; Crossref 10.1109/ICRA57147.2024.10610041 (pp. 11668-11675); arXiv 2310.05921.
- romer2025fiper — FIPER; arXiv 2510.09459 and NeurIPS 2025 poster page; proceedings volume/pages not confirmed, so omitted.
- hsu2024safetyfilter — The Safety Filter; Crossref 10.1146/annurev-control-071723-102940 (vol 7, pp. 47-72); arXiv 2309.05837.
- santos2025updating — Crossref 10.1109/ICRA55743.2025.11127680 (pp. 7778-7785); arXiv 2409.14580.
- wang2025robosafe — arXiv 2512.21220 (v2 2025-12-26); abstract page lists no venue (a search listing suggested ICLR 2026, not opened), so cited as preprint.
- yadav2025findingdory — arXiv 2506.15635; abstract page lists no venue (v2 PDF may say ICLR 2026, unconfirmed), cited as preprint.
- chen2024agentpoison — arXiv 2407.12784; NeurIPS 2024 poster page. An LLM-agent paper; the text does not claim robotics results.
- wu2025abstaineqa — arXiv 2512.04597 (cs.CV, cs.RO cross-list), no venue. The 42.79% best abstention recall is quoted from the abstract.
- wang2025fasdd — Crossref 10.1080/10095020.2024.2347922 (Geo-spatial Inf. Sci. 28(2):511-526). The published title differs from the ESSD preprint title. Dataset size is not quoted in the text because it was not checked against the paper.
- seidel2025wildfirevlm — Crossref 10.3390/drones9050347 (Drones 9(5):347); abstract read via Crossref.
- snyder2025policycomparison — arXiv 2503.10966 ("Accepted to RSS 2025"); RSS XXI proceedings page; DOI 10.15607/RSS.2025.XXI.077 taken from the proceedings page.
- li2024simpler (SIMPLER) — arXiv 2405.05941; PMLR 270:3705-3728 (CoRL 2024).

Fixes to existing entries (same date):
- CoRL year convention: all CoRL entries now carry the conference year (agia2025sentinel and kim2025openvla 2025 -> 2024; huang2023innermonologue and ichter2023saycan 2023 -> 2022; the PMLR volume year is kept in the note field). Existing BibTeX keys were left unchanged to avoid touching the introduction.
- liang2024introspective was uncited; it is now cited in the supplement (extended related work, KnowNo paragraph). Not independently re-verified beyond the earlier entry (arXiv 2402.06529, "NeurIPS 2024").
- zhou2025codeasmonitor, kadavath2022know and sun2026memorylies are now described as in their abstracts (VLM-generated-program constraint monitor, not specific to learned policies; reasonably calibrated on formatted multiple-choice questions; FrozenLake-style grid-world study).

## 8. Object search with priors / semi-static maps (checked 2026-10-17)
Method: titles, authors, venue, pages and DOIs from the Crossref API; abstracts from arXiv or Semantic Scholar where available (no abstract was available for Aydemir 2013 and Mason & Marthi 2012, so the text describes them only at the level of their titles). IEEE Xplore pages were not fetched. Positioning claims are hedged ("to our knowledge"); the full texts of these works were not read.
- aydemir2013active — Crossref 10.1109/TRO.2013.2256686 (T-RO 29(4):986-1002).
- wandzel2019mos — Crossref 10.1109/ICRA.2019.8793888 (pp. 7194-7200); abstract (Semantic Scholar): OO-POMDP, belief factorised into independent object distributions, Multi-Object Search.
- zeng2020slim — Crossref 10.1109/ICRA40945.2020.9196830 (pp. 1984-1990); arXiv 2006.10807 abstract: belief over target and landmark locations with inter-object spatial relations.
- mason2012objectworld — Crossref 10.1109/IROS.2012.6385729 (pp. 3851-3858).
- rosen2016lifelong — Crossref 10.1109/ICRA.2016.7487237 (pp. 1063-1070); abstract: feature persistence model for semi-static environments.
- zhou2023esc — ICML 2023, PMLR 202:42829-42842 (proceedings page); arXiv 2301.13166; abstract: pre-trained commonsense/vision-language models as soft constraints for zero-shot object navigation.
- yokoyama2024vlfm — Crossref 10.1109/ICRA57147.2024.10610712 (pp. 42-48); arXiv 2312.03275 abstract: VLM-based value map to choose frontiers.
- yan2025dovsg (DovSG) — Crossref 10.1109/LRA.2025.3547643 (RA-L 10(5):4252-4259); arXiv 2410.11989 ("Accepted by RA-L 2025"); abstract: local updates of a dynamic open-vocabulary 3D scene graph.
- Considered but dropped: Kunze et al., ICRA 2012 (10.1109/ICRA.2012.6224965; exists, but its content was not verified); Wong et al., ICRA 2013 (10.1109/ICRA.2013.6630966; occluded-object search by manipulation, less related).
- Not claimed anywhere: that these works lack safety analysis in general; the text only says that, to our knowledge, they do not bound stale-memory risk at a pre-action gate.
