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

## 9. Untrusted inputs: attacks and structural defences (I-19; checked 2026-10-17)
Method: titles, authors, comments/venue from the arXiv abstract pages (all opened); DOI/pages/venue from Crossref where noted. Descriptions follow the abstracts only; full texts were not read. Positioning claim for all: ours is a typed advice interface at a perception-grounded pre-action gate (advice can reorder or tighten, never relax), with a proven bound (advice monotonicity) and closed-loop evaluation (studies A, S); the works below are attacks, or filters/guardrails/certification, or capability separation in software agents.
Already in the bib (re-verified): robey2025jailbreaking (RoboPAIR; ICRA 2025 pp.11948-11956, Crossref); ravichandran2026guardrails (RoboGuard; RA-L is confirmed: Crossref lists RA-L 11(4):4649-4656, April 2026, DOI 10.1109/LRA.2026.3667488); chen2024agentpoison (AgentPoison, NeurIPS 2024).
- robey2025jailbreaking — RoboPAIR jailbreaks of LLM-controlled robots. Differs: attacks the planner's text channel; we assume such attacks and bound what instruction text can do at the gate.
- ravichandran2026guardrails — RoboGuard: a root-of-trust LLM grounds safety rules, a second stage checks plans (temporal logic). Differs: a guardrail on the plan generated from the context; ours places the check on the perceived scene at the station and gives advice no way to relax it.
- zhang2025badrobot — arXiv 2407.20242 (v5); "Accepted to ICLR 2025. Please cite the conference version." Voice-based jailbreak of embodied LLMs (VoxPoser, Code as Policies, ProgPrompt). Differs: attack on the planner; no pre-action perception gate.
- lu2024poex — arXiv 2412.16633. v1 title "POEX: Policy Executable Embodied AI Jailbreak Attacks" (checked on the v1 abstract page); latest version (v5, 2026-10-01) retitled "Easier Said Than Done: ..." and "Accepted by NDSS 2027", so cited as arXiv with both titles in the note. Proposes pre- and post-planning checks as mitigations; differs: those are prompt/LLM-level checks, not a typed interface with a bound.
- samarakoon2026paper — arXiv 2608.05715 (v1, 2026-08-06), no venue. Four-category taxonomy of printed-text injection, 5,670 trials, 3 VLMs, mitigations (prompt defence, two-stage verification, text masking). Closest to study S. Differs: they mitigate by filtering text; we separate advice from perception and report the residual vulnerability of scene text, which no structural argument covers.
- dorzhiev2026ripa — arXiv 2606.28649 (v1, 2026-06-26), single author, no venue. Injection through OCR/audio/LiDAR into LLM-controlled ROS 2 robots; a semantic firewall bypassed in 10.2% of obfuscated trials. Differs: filter-based defence; open-loop attack success rates.
- burbano2026chai — arXiv 2510.00181 (v2 2026-02-07): "Accepted at the IEEE Conference on Secure and Trustworthy Machine Learning (SaTML)"; the proceedings entry was not opened, so the year is taken as 2026 from the v2 date. Fake signs hijack drones/driving/robotic vehicles. Differs: attack paper; argues defences must go beyond adversarial robustness; ours is one such defence for the advice channel only.
- jones2025vla — arXiv 2506.03350 (2025-06-03), no venue listed. Jailbreak-style text attacks reach the full action space of VLAs. Differs: no defence offered in the abstract; model-level.
- cheng2024typographic — ECCV 2024, LNCS pp.179-196, DOI 10.1007/978-3-031-73202-7_11 (Crossref); arXiv 2402.19150. Typographic attacks transfer to LVLMs; abstract reports a drop from 42.07% to 13.90% with their findings applied. Supports treating scene text as a perception-level attack (study S).
- greshake2023indirect — AISec 2023, pp.79-90, DOI 10.1145/3605764.3623985 (Crossref); arXiv 2302.12173. Indirect prompt injection: data and instructions blur. We cite it as the origin of the threat model.
- dong2025minja — MINJA; arXiv 2503.03704 (v5 2026-02-12, comments only "Code released"); NeurIPS 2025 (Advances in NeurIPS 38), DOI 10.52202/085713-1554 (Crossref record found by title search). Memory injection through queries only. Differs: attack on software-agent memory; our memory is advice that cannot relax a check, so poisoning costs at most wasted visits and extra refusals.
- debenedetti2025camel — CaMeL; arXiv 2503.18813 (v2 2025-06-24), no venue listed, cited as preprint. Separates control and data flow of the trusted query and uses capabilities on tool calls; 77% of AgentDojo tasks with provable security vs 84% undefended. Closest conceptual analogue to "advice cannot relax": a structural (not filter) defence. Differs: software agents and tool calls; ours is a typed advice interface at a perception gate.
- costa2025fides — Fides; arXiv 2505.23643 (v2 2025-09-03), no venue listed. Information-flow control (confidentiality/integrity labels, deterministic policy enforcement) for agent planners, evaluated on AgentDojo. Differs: software agents; the label-based integrity idea is the analogue of our untrusted-advice flag.
- liu2026embodiedsecurity — arXiv 2608.16843 (v1 2026-08-17), survey, no venue. Twelve attack surfaces; "context and long-term memory" and multi-agent communication called underexplored; defences concentrate on action-level and runtime protection. Used only as a pointer that memory and peer channels are open surfaces.
- Considered but dropped: surveys of agent memory poisoning (2026 arXiv preprints such as 2603.20357, 2607.06595) were seen in search listings only; their abstract pages were not read, so not cited. "RoboGuard" venue is verified above; the Goh et al. multimodal-neurons typographic attack was not checked.

## 10. Literature review additions (checked 2026-10-17; see LITERATURE_REVIEW.md)
Method: arXiv API for titles, author lists, comment and journal-reference fields; Crossref for DOI, volume, pages; PMLR, NeurIPS, AAAI and KR proceedings pages for
venue and pages (PMLR citation metadata for Greenblatt, Kambhampati, Laroche, Antoniadis; kr.org page for SafeTap). Papers were retrieved as arXiv HTML into a scratch folder and read at
the passages named in LITERATURE_REVIEW.md. "Full text read" means the whole paper was retrieved and the cited sections were read, not every line; "abstract only" means only the
abstract (or a search listing) was read. IEEE Xplore and ACM pages were not opened. No existing key was changed; 44 keys were added, no duplicate key or eprint.

Algorithms with predictions
- lykouris2021competitive — JACM 68(4), 1-25, DOI 10.1145/3447579 (Crossref). Full text read (arXiv 1802.05399 v4): Sec. 1, 2.2, 3.
- purohit2018improving — NeurIPS 2018, vol 31, pp. 9661-9670 (page range from the NeurIPS proceedings listing). Read via the extended arXiv version 2407.17712 (Sec. 1); the conference text itself was not opened.
- mitzenmacher2020algorithms — CUP chapter pp. 646-662, DOI 10.1017/9781108637435.037 (Crossref); arXiv 2006.09123. Full text read, Sec. 1-2.
- antoniadis2023online — ACM TALG 19(2), 1-34, DOI 10.1145/3582689 (Crossref); ICML 2020 version PMLR 119:345-355 (PMLR page). Abstract only.
- li2022robustness — POMACS 6(1), 1-35, DOI 10.1145/3508038 (Crossref); arXiv 2106.09659. Full text read: abstract, Sec. 1, Thm 2.2.
- dinitz2021faster — NeurIPS 2021 (vol 34); arXiv 2107.09770; the page range was not verified, so it is omitted. Full text read: abstract and Sec. 1.
- eberle2022robustification — AAAI 36(9), 9732-9740, DOI 10.1609/aaai.v36i9.21208 (Crossref). Full text read: abstract, Sec. 1.
- gouleakis2023learning — AAAI 37(10), 11989-11996, DOI 10.1609/aaai.v37i10.26414 (Crossref). Abstract only (search listing).
- xu2023untrustworthy — arXiv 2309.16161, no venue found (comment and journal-reference fields empty). Full text read: abstract, Sec. 1.

Safe use of untrusted priors and advice
- laroche2019safe — SPIBB, ICML 2019 (PMLR 97:3652-3661, PMLR page); arXiv 1712.06924 comment: "accepted as a long oral at ICML2019". Abstract only.
- wendl2026sooper — arXiv 2601.19612, no venue. Abstract only.
- asmar2025learning — arXiv 2511.12378, no venue. Abstract read, text searched for safety terms (none found).
- fawzi2014secure — IEEE TAC 59(6), 1454-1467, DOI 10.1109/TAC.2014.2303233 (arXiv journal-reference field). Abstract only.

Runtime assurance, shielding, verification, evaluation of defences
- mehmood2022blackbox — NASA Formal Methods 2022, pp. 231-250 (arXiv journal-reference field only; Crossref not queried); arXiv 2102.12981. Full text read: abstract, Sec. 1, 2.2.
- ramadge1987supervisory — SIAM J. Control Optim. 25(1), 206-230, DOI 10.1137/0325013 (Crossref). Not read.
- kambhampati2024llmmodulo — ICML 2024, PMLR 235:22895-22907 (PMLR citation metadata); arXiv 2402.01817. Full text read: Sec. 1, 3.
- greenblatt2024control — ICML 2024, PMLR 235:16295-16336 (PMLR citation metadata); arXiv 2312.06942. Full text read: abstract, Sec. 1.
- yang2024safetychip — ICRA 2024, pp. 14435-14442, DOI 10.1109/ICRA57147.2024.10611447 (Crossref). Text retrieved but not read; description from a search listing.
- wang2026agentspec — arXiv 2503.18666; arXiv comment "Accepted by ... ICSE 2026", journal-reference "Proc. ICSE'26, pages 2938-2950. ACM, 2026" (taken from arXiv, the ACM page was not opened). Full text read: abstract, Sec. 1.
- obi2026safegate — arXiv 2604.05427 (title on arXiv contains "&": rendered as \&), no venue. Full text read: abstract, Sec. 1, decision rules.
- rodriguez2026safetap — KR 2026 (23rd Int. Conf. on Principles of KR&R), pp. 1109-1120, DOI 10.24963/kr.2026/104 (proceedings page citation metadata). Full text read: abstract, Sec. 1.
- hafez2025safe — arXiv 2503.03911, no venue. Abstract only.
- nasr2025attacker, wallace2024hierarchy, debenedetti2024agentdojo — arXiv 2510.09023, 2404.13208, 2406.13352; no venue taken from the arXiv records (AgentDojo is NeurIPS 2024 Datasets and Benchmarks per common knowledge, proceedings entry not checked). Abstracts only.

Information-flow control, capabilities, agent security
- denning1976lattice — CACM 19(5), 236-243, DOI 10.1145/360051.360056 (Crossref). Not read.
- biba1977integrity — MITRE Technical Report MTR-3153, 1977 (no DOI; report number from memory of the standard citation, not machine-checked). Not read.
- saltzer1975protection — Proc. IEEE 63(9), 1278-1308, DOI 10.1109/PROC.1975.9939 (Crossref). Not read.
- sabelfeld2003language — IEEE JSAC 21(1), 5-19, DOI 10.1109/JSAC.2002.806121 (Crossref; published 2003, DOI carries the 2002 manuscript year). Not read.
- birgisson2014macaroons — NDSS 2014, DOI 10.14722/ndss.2014.23212 (Crossref and NDSS programme page). Abstract read (search listing).
- willison2023dual — blog post 2023-04-25; identified through a search listing, the page itself was not opened.
- beurerkellner2025patterns — arXiv 2506.08837, no venue. Full text read: abstract, Sec. 1 and pattern descriptions (partly).

Memory
- louck2026tma — arXiv 2606.24322, single author, no venue. Full text read: abstract, act-gate design, theorem statements (partly).
- karunanidhi2026utility — arXiv 2608.21230, single author, no venue. Abstract only.
- wei2025amemguard — arXiv 2510.02373, no venue found on the arXiv record. Abstract only.
- nguyen2026openbelief — arXiv 2608.13923, no venue. Full text read: abstract, Sec. 1, method.
- zhang2026igvrrt — arXiv 2603.21887, no venue. Abstract only.

Scene text, multi-agent robots, concurrent work
- chang2026trustboundary — arXiv 2604.19844, no venue. Full text read: abstract, Sec. I-II, V (Table V header).
- liu2026breaking — arXiv 2608.16806 (v1 title "Breaking Planner Integrity Boundary: Enviroment State-Text Injection..." with the typo corrected here; a mirror lists the title "When State Becomes an Attack Surface"); 10 authors from the arXiv API, no venue. Full text read: abstract, Sec. 1, future work.
- nagaraja2026prompts — arXiv 2608.00747, no venue. Abstract only.
- li2026devil — arXiv 2607.10269, no venue. Abstract only.

Active perception, evaluation practice
- hu2026oanbv — arXiv 2603.11072, no venue. Abstract only.
- he2026detector — arXiv 2607.13361, single author, 12 pages, no venue. Abstract only.
- spitale2023reproducibility — arXiv 2309.01822, no venue checked. Full text read: Sec. 3.4.2 ("Only 3.38% of the 296 manuscripts ... reported that they pre-registered their works").

Re-reads of entries already in the bib (no entry changed):
- debenedetti2025camel, costa2025fides — upgraded from abstract-level to full text read (CaMeL Sec. 1, 3, 3.1, 5, 7, 9; Fides Sec. 1, 4.1, 4.3, 4.4, 5, 8). Fides states integrity non-interference for the binary integrity lattice (Sec. 4.4) and policy P-T (Sec. 4.3).
- ravichandran2026guardrails (RoboGuard) — full text read (abstract, Sec. I-III, V); the limitation "requires an accurate world model" is quoted in the review.
- wang2025robosafe (RoboSafe) — full text read (Sec. 4.1-4.2, 5.2); memory items add blocking predicates (Eq. 6-7).
- oloo2026vaptamp — see section 7; re-read Sec. II-IV for the review.
- samarakoon2026paper, burbano2026chai, liu2026embodiedsecurity — full text read at the sections cited in the review (mitigations D1-D3; Defenses discussion; Sec. 7.2).
- ren2023knowno — full text read (Sec. 3, appendix prompts): option randomisation and MCQA letter bias are in the appendix. Venue is CoRL 2023 (the bib already says 2023).
- ren2024exploreuntil, sun2026memorylies, yin2026glove, tang2026vlmdewm — abstracts re-read only.

Not cited (seen but unverified or not read): "VIRUS" (ICML 2026 poster on persistent memory poisoning of zero-shot object-navigation agents; no arXiv or proceedings text found), MemSentry (arXiv 2609.08747; retrieved, not read), ADMITBench (arXiv 2608.03866; industrial LLM advisories, white paper, only loosely related), Synergistic Simplex (arXiv 2605.08190; abstract only), CAPMAS (arXiv 2609.06500, capability delegation for multi-agent systems; listing only).
