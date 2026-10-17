# Literature check for I-24 (advice credit, Proposition 3)

Date of search: 2026-10-17. Searcher: Sonnet 5.5 research pass (read-only; no code run except a 10-line hand model, see Sec. 4.1).
Scope: 2015-2026 plus classical foundations. Already cited in the paper and in `LITERATURE_REVIEW.md` (not repeated here as new
works): Lykouris-Vassilvitskii, Purohit et al., Mitzenmacher-Vassilvitskii, Antoniadis et al. (untrusted predictions), Li et al. (LQ control),
Dinitz et al., Eberle et al., Gouleakis et al., Xu et al. (MetaBSG), Asmar-Kochenderfer (learning to trust), Black-Box Simplex, Fides, CaMeL,
Seto/Sha Simplex, shields, Biba/Denning.

How "verified" is used below. **V-abs** = the arXiv/PMLR/NeurIPS abstract page was fetched and title, authors and abstract were read.
**V-doi** = title, authors, venue, year, volume, pages confirmed through a Crossref record. **V-list** = confirmed only in a search
listing (not fetched). No paper below was read in full except part of Chen et al. 2026 (HTML, summarised by a fetch model, first
100k of 141k characters). Statements about "what a paper does not do" are therefore statements about abstracts and one HTML
extract, and should be re-checked before being used as a hard "to our knowledge" claim. The search tool is US-only.

## 0. Verdict in five lines

1. **Proposition 3 as a bound is not new in form**: "admission only if a bounded balance can pay the worst-case cost; refill from verified
   outcomes; cumulative price <= burst + rate x time" is a token-bucket / (sigma, rho) regulator (Cruz 1991). The refund-on-success part has
   the shape of alpha-investing wealth (Foster-Stine 2008), and "spend a budget earned from the baseline's own performance" is the
   conservative-bandit and the new learning-augmented-paging "prediction budget" idea. Say so in the paper; it is the honest name.
2. **No work found** that puts per-source, per-pool worst-case-cost credit in front of an *untrusted-advice channel of a physical or LLM-driven agent*,
   settles it from the agent's *own* safety check, and proves an additive bound over missions against adaptive sources while safety stays
   exactly Proposition 2 (credit is free in safety). That combination, with the non-farmable settlement rules (no refund for confirmed
   hazards; shadow confirmation of throttled claims), is the defensible novelty. Threat to novelty: **low** for the system claim, **medium** for the
   claim "Proposition 3 is a theoretical contribution" (a theory reviewer will call the proof an amortisation).
3. The learning-augmented literature has the *switching-on-observed-error* idea and, as of May 2026, an explicit "budget" primitive
   (Chen et al. 2026), but its guarantees are multiplicative competitive ratios inside one instance, not additive prices across repeated
   episodes against an adaptive source with a recovery rate.
4. A **matching lower bound is easy and not in the literature we found**: any rule that must re-admit a source after L confirmed throttled claims
   can be forced to waste floor(m/(L+1)) visits (Sec. 4.1). I-24's rho_shadow = 0.25 (L = 4) gives upper bound 0.25 m + 2 and lower bound
   about 0.2 m. This is the consistency-robustness trade-off in one line. It is my derivation, not a citation; it should become Proposition 4.
5. Biggest reviewer attack on I-24 itself: the **Sybil clause** (Sec. 4.3). Signed peer ids each get a fresh account with full credit C, so the price
   is C times the number of identities an attacker can mint.

---

## 1. Table of the most relevant works

Threat to novelty is for the claim "advice credit with a cumulative-price bound is new for untrusted advice to a safety gate".

| # | Work (full citation) | Venue / year | URL / DOI (status) | Relevance (one line) | Threat | Reason |
|---|---|---|---|---|---|---|
| 1 | Chen, P., Zhao, H., Tang, X., Wang, Y., Deng, S. Towards Optimal Robustness in Learning-Augmented Paging. | arXiv 2606.01342 v3, June 2026 (listed as ICML 2026 submission; not peer-reviewed) | https://arxiv.org/abs/2606.01342 (V-abs + partial HTML) | Fixes a robust baseline, keeps a non-negative "relative prediction budget" earned from the baseline's behaviour and spent on prediction-driven actions; robustness H_k+O(1). | **medium** | Closest *vocabulary and mechanism* (budget earned, budget spent, deviate only if affordable). But single instance, multiplicative ratio proved by a potential function, budget reset on each miss, no per-source accounts, no adversarial recovery rate, no safety gate. |
| 2 | Antoniadis, A., Coester, C., Eliáš, M., Polak, A., Simon, B. Mixing predictions for online metric algorithms. | ICML 2023 (arXiv 2304.01781, V-abs; venue from the ICML 2023 proceedings is **unverified**, the arXiv page lists none) | https://arxiv.org/abs/2304.01781 | Combines several predictors whose accuracy changes over time; benchmark is a *dynamic* (switching) combination; O(l^2) is optimal; (1+eps) if the number of switches is limited. | medium | Same issue as recovery: a comparator that may switch costs more, with a lower bound. Different objective (competitive ratio vs best predictor mixture), no worst-case cost reservation. Useful for the "switching comparator" framing of Prop. 4. |
| 3 | Anand, K., Ge, R., Kumar, A., Panigrahi, D. Online Algorithms with Multiple Predictions. | ICML 2022, PMLR 162:582-598 | https://arxiv.org/abs/2205.03921 (V-abs) | Competes with the best of several predictors, then robustifies against the prediction-free algorithm. | low | One instance, covering problems, no repeated-source accounting. Good citation for "several advice sources". |
| 4 | Wei, A., Zhang, F. Optimal Robustness-Consistency Trade-offs for Learning-Augmented Online Algorithms. | NeurIPS 2020 | https://arxiv.org/abs/2010.11443 ; https://papers.nips.cc/paper/2020/hash/5bd844f11fa520d54fa5edec06ea2507-Abstract.html (V-abs) | First non-trivial lower bounds for consistency-robustness (ski rental, non-clairvoyant scheduling); the model for our Prop. 4. | low | Competitive-ratio lower bounds; our trade-off is recovery lag vs additive price per mission. |
| 5 | Angelopoulos, S., Dürr, C., Jin, S., Kamali, S., Renault, M. Online Computation with Untrusted Advice. | ITCS 2020 (LIPIcs 151:52); arXiv 1905.05655 | https://arxiv.org/abs/1905.05655 ; DOI 10.4230/LIPIcs.ITCS.2020.52 (V-abs; DOI from search listing) | Advice may be adversarial; Pareto-optimal ski rental and bidding; lower bounds on trust vs. competitiveness. | low | Single run; no repeated interaction, so no notion of throttling a source. Cite for "untrusted advice" terminology. |
| 6 | Bhaskara, A., Cutkosky, A., Kumar, R., Purohit, M. Online Learning with Imperfect Hints. | ICML 2020, PMLR 119:822-831 | https://arxiv.org/abs/2002.04726 (V-abs) | Regret interpolates between "hints always good" and "no hints" without knowing hint quality; near-matching lower bounds. | low | Regret in OLO; hints are vectors. Closest *online-learning* statement of "oblivious to quality, degrades gracefully, lower bound". |
| 7 | Benomar, Z., Perchet, V. Advice Querying under Budget Constraint for Online Algorithms. | NeurIPS 2023 (vol. 36, pp. 75026-75047) | https://proceedings.neurips.cc/paper_files/paper/2023/hash/eda830e16044587b5082a853c4f25a90-Abstract.html (V-list) | A budget on how often advice can be *queried*. | low | Budget on consultation, not on the cost of trusting a source; no verification feedback. Mention to pre-empt "budgeted advice is known". |
| 8 | Chen, X., Chen, Y., Dai, S., Zhou, Y. AdaSwitch: An Adaptive Switching Meta-Algorithm for Learning-Augmented Bounded-Influence Problems. | arXiv 2509.02302 (v2 Oct 2026; no venue) | https://arxiv.org/abs/2509.02302 (V-abs) | Adaptively switches between offline and online oracles; guarantee improves as prediction error falls. | low | Switching on observed error, again inside one instance. |
| 9 | Cruz, R. L. A calculus for network delay, Part I: Network elements in isolation. | IEEE Trans. Inf. Theory 37(1):114-131, 1991 | https://doi.org/10.1109/18.61109 (V-doi) | The (sigma, rho) burstiness constraint: arrivals in any interval <= sigma + rho t; realised by a leaky/token bucket. | **medium (for naming)** | Proposition 3(a)(b) *is* an arrival-curve statement with burst C and rate rho. Not a threat to the application, but a reviewer who knows networking will see it at once; cite it and use the name. |
| 10 | Foster, D. P., Stine, R. A. alpha-investing: a procedure for sequential control of expected false discoveries. | JRSS-B 70(2):429-444, 2008 | https://doi.org/10.1111/j.1467-9868.2007.00643.x (V-doi; mechanics from search summaries) | Spend a "wealth" per test, earn wealth back on each discovery; controls marginal FDR over an unbounded stream of tests. | low-medium | Same refund-on-success accounting with a cap; different error (false discoveries) and no adaptive hostile source. Source of the "wealth" vocabulary. |
| 11 | Wu, Y., Shariff, R., Lattimore, T., Szepesvári, C. Conservative Bandits. | ICML 2016, PMLR 48:1254-1262 | https://proceedings.mlr.press/v48/wu16.html ; arXiv 1602.04282 (V-abs) | Keep cumulative reward above a fraction of a baseline at *every* step; falls back to the baseline when a confidence check fails; adversarial case costs more. | medium | Conceptually the nearest *bandit* statement: spend only what the baseline's performance has earned. Constraint is on reward, not on a bounded per-item worst cost; no sources, no verification by an independent gate. |
| 12 | Herbster, M., Warmuth, M. K. Tracking the Best Expert. | Machine Learning 32(2):151-178, 1998 | https://doi.org/10.1023/A:1007424614876 (V-doi) | Fixed-Share: mixing a share alpha back lets weights recover after a shift, at a per-round price. | low | The sleeping/shifting-expert counterpart of rho and rho_shadow: recovery rate = share rate. Cite for "recovery has a price". Matching lower bound for shifting regret not confirmed by me. |
| 13 | Freund, Y., Schapire, R. E., Singer, Y., Warmuth, M. K. Using and combining predictors that specialize. | STOC 1997, pp. 334-343 | https://doi.org/10.1145/258533.258616 (V-doi) | "Sleeping" experts that abstain; the throttled source is an expert that is put to sleep. | low | Different loss model; stochastic/adversarial regret, not worst-case admission. |
| 14 | Auer, P., Cesa-Bianchi, N., Freund, Y., Schapire, R. E. The nonstochastic multiarmed bandit problem. | SIAM J. Comput. 32(1):48-77, 2002 | https://doi.org/10.1137/S0097539701398375 (V-doi) | EXP3/EXP4: adversarial rewards and expert advice, regret O(sqrt(T)). | low | Standard "bandit with adversarial expert advice". Our guarantee is additive constant + linear-in-rho, i.e. a different regime on purpose (we may ignore the source entirely). |
| 15 | Mallmann-Trenn, F., Cavorsi, M., Gil, S. Crowd Vetting: Rejecting Adversaries via Collaboration with Application to Multi-Robot Flocking. | IEEE T-RO 38(1):5-24, 2022 | https://doi.org/10.1109/TRO.2021.3089033 (V-doi) | Robots use neighbours' opinions to flag Sybil/adversarial robots; detection time bounds. | low | Trust from *peer* consensus and physical-layer signals, not from the robot's own verification; no price bound. The main multi-robot trust citation. |
| 16 | Ballotta, L., Vékássy, Á., Gil, S., Yemini, M. Confidence Boosts Trust-Based Resilience in Cooperative Multi-Robot Systems. | arXiv 2506.08807, June 2025 (submitted to IEEE; not peer-reviewed) | https://arxiv.org/abs/2506.08807 (V-abs) | A confidence parameter trades coordination quality for speed under arbitrarily many malicious robots. | low | Same trade-off flavour in multi-robot trust; guarantee about coordination, not about a wasted-visit budget. |
| 17 | Douceur, J. R. The Sybil Attack. | IPTPS 2001, LNCS 2429:251-260 (Springer 2002) | https://doi.org/10.1007/3-540-45748-8_24 (V-list) | One entity presenting many identities defeats redundancy unless identity is certified. | medium (for our Sybil clause) | Says our per-peer account is exploitable unless peers are certified; see Sec. 4.3. |
| 18 | Friedman, E. J., Resnick, P. The Social Cost of Cheap Pseudonyms. | J. Econ. Manag. Strategy 10(2):173-199, 2001 | https://doi.org/10.1162/105864001300122476 (V-doi) | With free identities, the best equilibrium makes newcomers "pay their dues"; no equilibrium sustains more cooperation. | medium (for our Sybil clause) | Gives the fix and its price: lower initial credit for unknown ids. |
| 19 | Zhang, Q., Xiong, Z., Mao, Z. M. LLM Safeguard is a Double-Edged Sword: Exploiting False Positives for Denial-of-Service Attacks. | arXiv 2410.02916 (v3 Apr 2025) | https://arxiv.org/abs/2410.02916 (V-abs) | Attackers make safeguards refuse benign requests (97 % blocked on Llama Guard 3). | none | Establishes the threat that I-24 prices: a safety gate's false positives are an attack surface. Cite it as motivation. |
| 20 | Kravchenko, A. et al. APPA: Recoverable Information-Flow Control for Real-World LLM Agents. | arXiv 2607.24625 (v2 Aug 2026; not peer-reviewed) | https://arxiv.org/abs/2607.24625 (V-abs) | Monotone taint tracking over-blocks or strands the agent; APPA adds policy-governed *recovery*. | low | Same tension (strict IFC loses utility; recovery is needed) in software agents. No budget or credit mechanism per the abstract; recovery is policy-based. |
| 21 | Shi, T. et al. Progent: Securing AI Agents with Privilege Control. | arXiv 2504.11703 (v3 May 2026; no venue named) | https://arxiv.org/abs/2504.11703 (V-abs) | Least-privilege tool policies; an SMT check classifies each update as narrowing (automatic) or expanding (needs approval). | low | The "narrowing is free, expansion needs authority" rule is Proposition 2's twin; nothing per-source or cumulative. |
| 22 | Ren, S. et al. Reputation as a Solution to Cooperation Collapse in LLM-based MASs (RepuNet). | AAMAS 2026; arXiv 2505.05029 | https://arxiv.org/abs/2505.05029 (V-abs) | Direct and gossip reputation among LLM agents; exploitative agents get isolated. | low | Reputation from interaction outcomes in a cooperation game; no cost bound, no safety gate. |

(22 rows; rows 12-14 are classical foundations and may be cut to fit a page. TrustFlow, arXiv 2603.19452, a single-author preprint on
vector reputation propagation that claims to "resist sybil attacks", was checked at the abstract level and left out as weak evidence.)

---

## 2. Closest prior work and the precise delta

**Closest by mechanism**: Chen et al. 2026 (row 1) and the token-bucket calculus (row 9).

* Versus **learning-augmented switching / prediction budget** (rows 1, 2, 8, and the F&R / BlindOracle&LRU line that row 1 summarises):
  those algorithms keep a robust baseline and let a *prediction-driven* action happen only when a balance earned from the baseline's
  observed behaviour permits it. I-24 shares this shape. The delta is five-fold.
  (i) **Currency and object**: the balance is in worst-case *visits and false refusals*, reserved per admitted item before the mission, not a
  competitive-ratio potential.
  (ii) **Free in safety**: in their setting, switching to the baseline is what makes the algorithm robust; here robustness (Proposition 2) holds
  for every admitted subset by construction, so credit buys only availability, and its correctness never enters a safety argument.
  (iii) **Repeated episodes and per-source accounts**: the guarantee is additive and cumulative over missions against any adaptive source, with an
  explicit recovery rate (rho, rho_shadow); the paging budget resets on a miss and the guarantee is per instance.
  (iv) **Settlement by an independent check**: credit is moved only by the robot's own gate (reorder confirmed or wrong; caution-only refusal),
  with settlement rules chosen to be non-farmable (no refund for confirmed hazards, since the robot would have refused anyway; refunds
  capped; shadow confirmation of *throttled* claims so that a locked-out source can come back at no cost).
  (v) **Sybil-aware identity**: unauthenticated channels share one account.
* Versus **token bucket / network calculus** (row 9): the same arithmetic (cumulative cost <= sigma + rho t). The delta is the application: the
  bucket is refilled not by time alone but by verified outcomes (refund) and by shadow checks, and its tokens are consumed by the
  *worst-case effect of an item on a safety gate* rather than by packet size. Say "(sigma, rho) regulator" in the text.
* Versus **conservative bandits** (row 11): both let the learner deviate from a baseline only up to what the baseline's performance
  has earned. There the constraint is on cumulative reward at every step and the deviation is the learner's own exploration; here the deviation is
  imposed by an untrusted third party and each deviation has a known bounded worst-case cost.
* Versus **alpha-investing** (row 10): wealth earned back on success, bounded spending. There the error is false discoveries in expectation; here a
  deterministic bound against an adversary.
* Versus **robot / LLM-agent trust** (rows 15, 16, 22): trust there is estimated from peer consensus, physical-layer signals, or gossip;
  ours is settled from the robot's own perception-grounded check, and what we bound is a cost, not a detection rate.

**Closest by threat model**: Zhang et al. 2024 (row 19) is the attack that I-24 prices; APPA (row 20) is the closest defence-side statement
that strict monotone defences need a controlled way back.

## 3. Paste-ready related work (LaTeX)

```latex
\textbf{Pricing untrusted advice over time.}
Advice credit is, in form, a $(\sigma,\rho)$ regulator~\cite{cruz1991calculus}: each source holds a bounded balance, an item is admitted only if
the balance can pay its worst-case cost, and the cumulative price is at most a burst $C$ plus a rate $\rho$ per mission against any adaptive source
(Prop.~\ref{prop:price}). Learning-augmented algorithms also fall back to a robust baseline once predictions have proved costly, and
recent work makes the earned ``budget'' for following predictions explicit~\cite{lykouris2021competitive,antoniadis2023online,chen2026paging};
they compete with the best or a switching mixture of predictors~\cite{anand2022multiple,antoniadis2023mixing}, and their trade-offs between trust
and robustness have matching lower bounds~\cite{wei2020optimal,angelopoulos2020untrusted}.
These results bound a competitive ratio within one instance, whereas ours is an additive bound over repeated missions, per source, for a gate
whose safety does not depend on the admission rule, so throttling costs only availability, the attack surface that false-positive attacks on
safeguards exploit~\cite{zhang2024safeguarddos}. Spending only what a baseline has earned is also the idea of conservative
bandits~\cite{wu2016conservative}, and wealth that grows with verified successes that of $\alpha$-investing~\cite{foster2008alpha}; unlike
reputation in multi-robot and multi-agent systems~\cite{mallmanntrenn2022crowd,ren2026repunet}, credit is settled from the robot's own
check, never from peers, and the recovery rate is the explicit price of consistency. Free identities defeat any per-identity account~\cite{douceur2002sybil,friedman2001cheap}, so unauthenticated channels share one account.
```

(6 sentences. If a lower-bound proposition is added, append: "Any rule that re-admits a throttled source after $L$ confirmed claims can be
forced to waste $\lfloor m/(L+1)\rfloor$ visits, so the recovery rate trades consistency against robustness as in
\cite{wei2020optimal}." Remove `\cite{antoniadis2023mixing}` if the ICML venue stays unverified and cite it as arXiv.)

## 4. What would make Proposition 3 stronger, and what a reviewer will demand

### 4.1 A matching lower bound (recommended: make it Proposition 4)

*Claim (derived here; not found in the literature).* Let A be any deterministic admission rule for one source, with one location claim per mission, that is
**L-recoverable**: whenever the L most recent claims were all confirmed by the robot's own check (whether admitted or throttled, revealed at
no cost), A admits the next claim. Then an adaptive adversary can force A to waste at least floor(m/(L+1)) visits in m missions.
*Proof sketch.* The adversary sends a true claim whenever A throttles and a false claim whenever A admits. Any L+1 consecutive missions
contain an admission (otherwise L consecutive confirmed claims were followed by a throttle, contradicting L-recoverability), and every admission
is false and costs one visit. Revealing the outcome of throttled claims for free only helps A, so the bound holds a fortiori for
I-24, where a shadow confirmation needs the robot's own search to reach the station.
*Tightness.* In I-24 an exhausted source needs 4 shadow confirmations at rho_shadow = 0.25 to reach credit 1, so L = 4 and the lower bound
is m/5 against the upper bound 0.25 m + 2. A hand model of the location pool (C = 2, refund 1, shadow 0.25, adversary false iff admitted)
gave 3, 21, 201 wasted visits for m = 10, 100, 1000 (about 0.2 m + 1), against bound 4.5, 27, 252. Not run on the real module.
*Reading.* Recovery lag L and adversarial waste rate 1/(L+1) are inverse: the consistency-robustness curve of the sweep is the
frontier, and no mechanism of this class can be below it. Open: randomised rules against an oblivious adversary; rules that use the
*content* of claims (e.g. plausibility priors) to break the symmetry.
Related lower-bound technology: Wei-Zhang (row 4), dynamic-comparator lower bound of Antoniadis et al. (row 2), Bhaskara et al. (row 6).

### 4.2 Other points a reviewer is likely to raise

1. **Name the mechanism**: (sigma, rho) / token-bucket regulator (Cruz); wealth in the sense of alpha-investing; "forgiveness rate" for rho
   (generous tit-for-tat, Nowak-Sigmund, Nature 355:250-253, 1992, DOI 10.1038/355250a0, V-doi; not in the table). Recovery as Fixed-Share.
2. **Benchmark**: state Proposition 3 as "the net price of the source relative to ignoring it is at most C + rho m" (it is not a bound relative to always following,
   which can be better), and give the *consistency* side quantitatively: for a source with accuracy q the credit walk has drift q r - (1-q) per claim, so it is mostly
   admitted iff q > 1/(1+r) (r = refund). With r = 1 the break-even is q = 1/2 even if a correct reorder saves less than one visit on average;
   the 70 %-correct row of the descriptive model shows the loss. Suggest r = the estimated saving per confirmed reorder, so admission iff the
   source is net-positive, and report the break-even accuracy.
3. **Refund farming**: a refund only counts if the reorder changed the order (otherwise a source can bank credit by advising the station
   already first). The cap at C bounds banking to one burst. State both explicitly in the proof.
4. **Hazard side**: the one-sided design (no refund for confirmed hazards) makes the hazard pool a pure leaky bucket, which caps the price but
   also starves a *correct but unverifiable* hazard source (unseen fire). Reviewers will ask for the price of that on a true hazard;
   say that safety is unchanged (the base check still runs) and give the missed-early-warning cost as the consistency loss.
5. **Adversary model**: the bound is deterministic and holds for any adaptive sequence; contrast with the long-run guarantees of
   adaptive conformal inference (Gibbs-Candès, NeurIPS 2021, arXiv 2106.00170, V-abs), which also give assumption-free long-run bounds.
   A reviewer may ask whether the source can observe the ledger: yes, the bound assumes it can (the "adaptive liar" row).
6. **Closed-loop evidence**: the log lists the descriptive model as not yet closed-loop and unregistered. Wording must stay at "bounded by
   construction, measured in a model"; claim only what the pre-registered closed-loop run shows.
7. **Multi-source collusion**: sources are accounted separately; k colluding channels cost k(C + rho m). State it.

### 4.3 Sybil clause (the largest real gap)

`advice_credit.source_key` gives each signed `peer_id` its own account with full initial credit C. A peer that can mint signed identities
at will therefore multiplies the price by the number of identities (Douceur 2002; Friedman-Resnick 2001 show that free pseudonyms cannot
be fixed without making newcomers pay). Options, cheapest first: (a) a **global per-channel pool** that every peer account also draws from
(price <= C_channel + rho m regardless of identities); (b) newcomers start with less credit and earn the rest through confirmed advice;
(c) require identities to be certified outside the protocol, and state that as an assumption. The current text "one unauthenticated channel
cannot multiply its credit by inventing names" is correct only for unauthenticated channels; authenticated peers need (a), (b) or (c).

### 4.4 Gaps in this search (what I could not establish)

* No paper found that gives a *lower bound for recovery of a throttled source* in learning-augmented or reputation settings; my claim of
  novelty for 4.1 rests on a US-only search and abstracts. Quick check candidates not opened: Herbster-Warmuth shifting-regret lower bounds,
  Antoniadis et al. 2023 (row 2) full text, Chen et al. 2026 related work.
* No source found on *cumulative availability cost of runtime-assurance (Simplex) false alarms under adversarial triggering*. The nearest
  hits were Simplex architecture surveys without such a bound and the false-positive DoS paper (row 19); treat "to our knowledge no bound
  exists" as a search result, not a theorem.
* The "test before you trust" idea (Gouleakis, talk abstract at UC Irvine: statistically validate a prediction in a short testing phase before
  committing) is a talk listing only; I found no paper and did not include it.
* Rows 7, 17 are V-list only; row 2's ICML venue and row 5's DOI should be rechecked before submission.

---

## 5. BibTeX (new keys only; existing keys `lykouris2021competitive`, `antoniadis2023online` etc. are already in `references.bib`)

Verification marks are comments. Entries with `% UNVERIFIED:` have a field I could not confirm.

```bibtex
@article{cruz1991calculus,
  author  = {Cruz, Rene L.},
  title   = {A calculus for network delay, {Part I}: Network elements in isolation},
  journal = {IEEE Transactions on Information Theory},
  volume  = {37}, number = {1}, pages = {114--131}, year = {1991},
  doi     = {10.1109/18.61109}
} % V-doi (Crossref: "A calculus for network delay. I. Network elements in isolation", vol 37, pp 114-131, 1991); issue number 1 not shown by Crossref extract, UNVERIFIED

@article{chen2026paging,
  author = {Chen, Peng and Zhao, Hailiang and Tang, Xueyan and Wang, Yixuan and Deng, Shuiguang},
  title  = {Towards Optimal Robustness in Learning-Augmented Paging},
  journal = {arXiv preprint arXiv:2606.01342},
  year   = {2026}
} % V-abs; preprint, listed as an ICML 2026 submission; use @misc/@article arXiv if the style rejects this entry type

@inproceedings{antoniadis2023mixing,
  author = {Antoniadis, Antonios and Coester, Christian and Eli{\'a}{\v s}, Marek and Polak, Adam and Simon, Bertrand},
  title  = {Mixing predictions for online metric algorithms},
  booktitle = {Proceedings of the 40th International Conference on Machine Learning (ICML)},
  year   = {2023},
  note   = {arXiv:2304.01781}
} % V-abs for title/authors/arXiv id; the ICML 2023 venue is UNVERIFIED (arXiv page lists none). Safe fallback: cite as arXiv preprint.

@inproceedings{anand2022multiple,
  author    = {Anand, Keerti and Ge, Rong and Kumar, Amit and Panigrahi, Debmalya},
  title     = {Online Algorithms with Multiple Predictions},
  booktitle = {Proceedings of the 39th International Conference on Machine Learning},
  series    = {Proceedings of Machine Learning Research}, volume = {162}, pages = {582--598}, year = {2022},
  url       = {https://proceedings.mlr.press/v162/anand22a.html}
} % V-abs (arXiv 2205.03921) + PMLR listing

@inproceedings{wei2020optimal,
  author    = {Wei, Alexander and Zhang, Fred},
  title     = {Optimal Robustness-Consistency Trade-offs for Learning-Augmented Online Algorithms},
  booktitle = {Advances in Neural Information Processing Systems 33 (NeurIPS)},
  year      = {2020},
  note      = {arXiv:2010.11443}
} % V-abs + NeurIPS proceedings listing

@inproceedings{angelopoulos2020untrusted,
  author    = {Angelopoulos, Spyros and D{\"u}rr, Christoph and Jin, Shendan and Kamali, Shahin and Renault, Marc},
  title     = {Online Computation with Untrusted Advice},
  booktitle = {11th Innovations in Theoretical Computer Science Conference (ITCS)},
  series    = {LIPIcs}, volume = {151}, pages = {52:1--52:15}, year = {2020},
  doi       = {10.4230/LIPIcs.ITCS.2020.52},
  note      = {arXiv:1905.05655}
} % V-abs (arXiv); DOI from a search listing; volume/page numbers UNVERIFIED

@inproceedings{bhaskara2020hints,
  author    = {Bhaskara, Aditya and Cutkosky, Ashok and Kumar, Ravi and Purohit, Manish},
  title     = {Online Learning with Imperfect Hints},
  booktitle = {Proceedings of the 37th International Conference on Machine Learning},
  series    = {Proceedings of Machine Learning Research}, volume = {119}, pages = {822--831}, year = {2020},
  url       = {https://proceedings.mlr.press/v119/bhaskara20a.html}
} % V-abs (arXiv 2002.04726) + PMLR listing

@inproceedings{benomar2023advice,
  author    = {Benomar, Ziyad and Perchet, Vianney},
  title     = {Advice Querying under Budget Constraint for Online Algorithms},
  booktitle = {Advances in Neural Information Processing Systems 36 (NeurIPS)},
  pages     = {75026--75047}, year = {2023}
} % V-list (NeurIPS proceedings page in search results, not fetched)

@article{chen2025adaswitch,
  author  = {Chen, Xi and Chen, Yuze and Dai, Shibo and Zhou, Yuan},
  title   = {{AdaSwitch}: An Adaptive Switching Meta-Algorithm for Learning-Augmented Bounded-Influence Problems},
  journal = {arXiv preprint arXiv:2509.02302},
  year    = {2025}
} % V-abs; preprint

@inproceedings{wu2016conservative,
  author    = {Wu, Yifan and Shariff, Roshan and Lattimore, Tor and Szepesv{\'a}ri, Csaba},
  title     = {Conservative Bandits},
  booktitle = {Proceedings of the 33rd International Conference on Machine Learning},
  series    = {Proceedings of Machine Learning Research}, volume = {48}, pages = {1254--1262}, year = {2016},
  url       = {https://proceedings.mlr.press/v48/wu16.html}
} % V-abs (arXiv 1602.04282) + PMLR listing

@article{foster2008alpha,
  author  = {Foster, Dean P. and Stine, Robert A.},
  title   = {$\alpha$-investing: a procedure for sequential control of expected false discoveries},
  journal = {Journal of the Royal Statistical Society: Series B (Statistical Methodology)},
  volume  = {70}, number = {2}, pages = {429--444}, year = {2008},
  doi     = {10.1111/j.1467-9868.2007.00643.x}
} % V-doi

@article{herbster1998tracking,
  author  = {Herbster, Mark and Warmuth, Manfred K.},
  title   = {Tracking the Best Expert},
  journal = {Machine Learning}, volume = {32}, number = {2}, pages = {151--178}, year = {1998},
  doi     = {10.1023/A:1007424614876}
} % V-doi (issue number UNVERIFIED)

@inproceedings{freund1997specialize,
  author    = {Freund, Yoav and Schapire, Robert E. and Singer, Yoram and Warmuth, Manfred K.},
  title     = {Using and combining predictors that specialize},
  booktitle = {Proceedings of the 29th Annual ACM Symposium on Theory of Computing (STOC)},
  pages     = {334--343}, year = {1997},
  doi       = {10.1145/258533.258616}
} % V-doi

@article{auer2002nonstochastic,
  author  = {Auer, Peter and Cesa-Bianchi, Nicol{\`o} and Freund, Yoav and Schapire, Robert E.},
  title   = {The Nonstochastic Multiarmed Bandit Problem},
  journal = {SIAM Journal on Computing}, volume = {32}, number = {1}, pages = {48--77}, year = {2002},
  doi     = {10.1137/S0097539701398375}
} % V-doi (issue number UNVERIFIED)

@article{mallmanntrenn2022crowd,
  author  = {Mallmann-Trenn, Frederik and Cavorsi, Matthew and Gil, Stephanie},
  title   = {Crowd Vetting: Rejecting Adversaries via Collaboration with Application to Multirobot Flocking},
  journal = {IEEE Transactions on Robotics}, volume = {38}, number = {1}, pages = {5--24}, year = {2022},
  doi     = {10.1109/TRO.2021.3089033}
} % V-doi (Crossref: vol 38, pp 5-24, Feb 2022); issue number UNVERIFIED

@article{ballotta2025confidence,
  author  = {Ballotta, Luca and V{\'e}k{\'a}ssy, {\'A}ron and Gil, Stephanie and Yemini, Michal},
  title   = {Confidence Boosts Trust-Based Resilience in Cooperative Multi-Robot Systems},
  journal = {arXiv preprint arXiv:2506.08807},
  year    = {2025}
} % V-abs; preprint

@inproceedings{douceur2002sybil,
  author    = {Douceur, John R.},
  title     = {The Sybil Attack},
  booktitle = {Peer-to-Peer Systems (IPTPS 2002)},
  series    = {LNCS}, volume = {2429}, pages = {251--260}, year = {2002},
  publisher = {Springer},
  doi       = {10.1007/3-540-45748-8_24}
} % V-list (DOI and pages from search results; some sources date the workshop 2001)

@article{friedman2001cheap,
  author  = {Friedman, Eric J. and Resnick, Paul},
  title   = {The Social Cost of Cheap Pseudonyms},
  journal = {Journal of Economics \& Management Strategy}, volume = {10}, number = {2}, pages = {173--199}, year = {2001},
  doi     = {10.1162/105864001300122476}
} % V-doi

@article{zhang2024safeguarddos,
  author  = {Zhang, Qingzhao and Xiong, Ziyang and Mao, Z. Morley},
  title   = {{LLM} Safeguard is a Double-Edged Sword: Exploiting False Positives for Denial-of-Service Attacks},
  journal = {arXiv preprint arXiv:2410.02916},
  year    = {2024}
} % V-abs; preprint

@article{kravchenko2026appa,
  author  = {Kravchenko, Arseny and Liventsev, Vadim and Konstantinov, Innokentii and Iskhakov, Ildar and Kukuy, Matvey},
  title   = {{APPA}: Recoverable Information-Flow Control for Real-World {LLM} Agents},
  journal = {arXiv preprint arXiv:2607.24625},
  year    = {2026}
} % V-abs; preprint

@article{shi2025progent,
  author  = {Shi, Tianneng and He, Jingxuan and Wang, Zhun and Li, Hongwei and Wu, Linyu and Guo, Wenbo and Song, Dawn},
  title   = {Progent: Securing {AI} Agents with Privilege Control},
  journal = {arXiv preprint arXiv:2504.11703},
  year    = {2025}
} % V-abs; preprint (earlier title: "Programmable Privilege Control for LLM Agents")

@inproceedings{ren2026repunet,
  author    = {Ren, Siyue and Fu, Wanli and Zou, Xinkun and Shen, Chen and Cai, Yi and Chu, Chen and Wang, Zhen and Hu, Shuyue},
  title     = {Reputation as a Solution to Cooperation Collapse in {LLM}-based {MASs}},
  booktitle = {Proceedings of the 25th International Conference on Autonomous Agents and Multiagent Systems (AAMAS)},
  year      = {2026},
  note      = {arXiv:2505.05029}
} % V-abs (page says AAMAS 2026); booktitle edition number UNVERIFIED

@inproceedings{gibbs2021aci,
  author    = {Gibbs, Isaac and Cand{\`e}s, Emmanuel},
  title     = {Adaptive Conformal Inference Under Distribution Shift},
  booktitle = {Advances in Neural Information Processing Systems 34 (NeurIPS)},
  year      = {2021},
  note      = {arXiv:2106.00170}
} % V-abs + NeurIPS proceedings listing

@article{nowak1992tft,
  author  = {Nowak, Martin and Sigmund, Karl},
  title   = {Tit for tat in heterogeneous populations},
  journal = {Nature}, volume = {355}, pages = {250--253}, year = {1992},
  doi     = {10.1038/355250a0}
} % V-doi
```

Not included on purpose: Resnick-Zeckhauser-Friedman-Kuwabara, "Reputation systems", CACM 43(12):45-48, 2000
(DOI 10.1145/355112.355122, V-doi) is a possible general reference for reputation, add if a reviewer asks; Badanidiyuru-Kleinberg-Slivkins,
Bandits with Knapsacks, J. ACM 65(3), 2018 (DOI 10.1145/3164539, V-doi) is the budgeted-resource bandit framework and a possible citation
for "resources consumed per action with a global budget"; it is not close enough to the mechanism to require citing.
