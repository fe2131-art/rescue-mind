# Copy-edit notes for `main.tex` and `supplement.tex` (RA-L/ICRA submission)

Scope: wording, grammar, consistency of terms and formats, captions, and page fit. No number, claim, argument, macro name, label,
reference or citation key was changed, and no `\IfPend...`, `\IfAnyPend`, `\IfSnapshot` or `\TBD` structure was touched
(`tests/test_snapshot_mode.py` passes; every `\Macro` and every `\ref`, `\label`, `\cite` occurs as often as before).
The only intentional removals are listed under "Duplicate details shortened for page fit".

## Systematic changes

1. **American spelling** (IEEE house style), in both files: behavior, generalize, randomized, stylized, analyzed, favorable/favored,
   defense(s), center, color(ed), gray, labeled, modeled, license, program, emphasizes, verbalizes, organized, recognized,
   realized, scrutinized, rationalized, synthesized, judgment, randomization, realization, optimize.
2. **Cross-reference style.** Main: `Supp.~Sec.~S10`, `Supp.~Table~S5` everywhere (was a mix of `Supp.~S10` and `Supp.~Sec.~S10`).
   Supplement: its own parts are cited without `Supp.` (`Fig.~S2`, `Sec.~S11`); one self-reference was replaced by "details below".
   Mid-sentence `Prop.~2`, `Obs.~1`; spelled out only at the start of a sentence.
3. **Terminology, one term per concept.**
   - *hazard refusal* (not "hazard stop"); *false refusal* (not "false stop") for a check that refuses a station it should approve;
     *false alarm* is kept for a single view flagged by the hazard question. The registered-claim quotation
     ``extra false stops $\le0.10$'' (supplement W-a3) is left verbatim because it quotes the registration.
   - *upper bound* (not "upper limit").
   - *tighten-only* (not "monotone" for the advice rule; "monotone loss" in the conformal-risk-control citation and the code name
     `assert_monotone` are unchanged).
   - *advice* (not "tip"); depot *stations* (a "bay" is a station on a pallet or low shelf, stated once; "visited bays" became "visited stations").
   - gate = the pre-action decision, check = one per station, as defined in Sec. I; the *acquisition gate* of study R (a frame-validity
     filter, and the "Gate rej." column header of the generated study-R table) is glossed at first use so that it is not read as the gate.
     Renaming the generated column header would need a change in `scripts/paper_numbers.py` and was not made.
   - *error budget*: now defined where it is first used ("the chance that it approves a station it should refuse"); `$\varepsilon_{\mathrm{any}}$`
     is the budget of the contribution sentence, unchanged.
   - the closed-set/permuted/look-around/fail-closed/pre-registered spellings were already uniform; hyphenation of
     *closed loop* (noun) and *closed-loop* (adjective) was fixed in two table cells.
4. **Run-ons split** (main body and supplement): the W paragraph (3 600 characters) now has sentence breaks at each result and each caveat;
   the "advice" definition, Observation 1, "Price", "What the evidence is", the study-A pilot sentence, the limits paragraph, the
   `Study V` paragraph and several one-sentence-per-clause lists. Elliptical clauses ("look-around \WMissLA{}") got their verbs.
5. **Tense.** Results and campaign descriptions in the past tense (campaign H design, study V, the H medians); definitions, rules and
   registered designs stay in the present tense.
6. **Parallel structure.** Intro list (1)-(5) now has parallel clauses; the two "supporting results" are parallel; telegraphic
   "Unsafe deliveries: ...", "Registered 95% interval ...: ...; observed ..." became full sentences (campaign J, study V).
7. **Headings.** Subsection titles are in IEEE title case in both files.
8. **Captions that stand alone.** Fig. 1 states what solid, dashed and thick boxes mean; Fig. 4 says what refuses and why; the study-R figure glosses the
   acquisition gate; Fig. 5 lost one explanatory sentence that the text states (see below).
9. **Number formatting.** Thin spaces (`1\,200`), en dashes in ranges and `vs.\` were already almost uniform; the three exceptions were fixed.
10. **Wording that overclaims or is colloquial** was neutralized without changing meaning: "What pre-registration bought us" ->
    "Value of pre-registration"; "the honest transfer result" -> "the transfer result to report"; "elementary by design" -> "kept
    elementary so that code and audit can enforce it"; "Whatever the numbers will be" -> "turn out to be". Hedges were not added or removed:
    the pending-study wording is as it was.

## Layout (page fit; main body must end on p. 8 in the submission snapshot)

Before this edit the snapshot body ended with the Conclusion at the top of p. 9. Changes that cost no content:
`microtype`, `\emergencystretch=1.5em`, tighter float separation (`\textfloatsep`, `\dbltextfloatsep`, `\floatsep`, `\intextsep`),
Fig. 5 width 0.95 -> 0.8 of the column, Fig. 3 width 0.6 -> 0.55 of the text width, Fig. 1 box height 2.75 -> 2.5 cm.
Supplement: the W-b comparison table (it was 418 pt wider than the column, an old overfull box) now uses fixed-width columns, and the two
`\texttt` names in the trust-base table can break.

## Duplicate details shortened for page fit (no claim removed)

- Intro: the list "(integrity non-interference, information-flow control, algorithms with predictions)" after "The principle itself is old" (the same sources are in Related Work).
- "What the evidence is": the list of the three bugs found by the proof review (all three are listed in Supp. Sec. S10, trust base).
- Sec. V Data: "(a blue crate, an orange traffic cone)" -> pointer to Supp. Sec. S1, where both are named.
- Fig. 5 caption: "The fire is small and partly hidden from the left, so the two p_h values are close." (the text says the fire is small from the side).
- Discussion: the duplicate "A second model did not help (J)" (the next sentences say J kept us from adopting a second model).

## Sentences where a factual problem is suspected and nothing was changed

1. Sec. II (last paragraph of "Untrusted inputs"): "a probabilistic perception gate on a **physical** robot". The title, Sec. VII and the conclusion say that
   everything is simulation.
2. Sec. V, "Registration and statistics" and Supp. S9 (Statistical): "Claims are not pooled across studies", while the abstract, Sec. VI-B and the conclusion
   report the memory result **pooled over H and V** (M0 1, M2 1, M1 40 of 82).
3. Sec. I (after the chain list): "we measure its price in time and refusals against naive and **filter** baselines in ground-truth-audited closed loop".
   The filter arm belongs to study A, which is registered and not run in the snapshot; consider an `\IfPendA` hedge here.
4. Hard-coded numbers in prose (not macros), which would go stale if a result file changes: "150 new worlds" (Plug-in budget), "16 worlds" and
   "16 perceivable fires" (G), "75 fire-free twins", "32" in "X/32" (H), "9 000 adversarial inputs", "all 11 injected relaxing bugs", "five bugs ... three more",
   "0.19" (Wilson bound of 0 of 16), "224 offline texts", "226 runs", "1.7 expected false refusals", "193 fire-free T2 views", "the calibrated threshold is 0.3 (P2)",
   "64/100", "Wilson upper bounds 11% and 16%", "8 relocation-persist pairs" (equals `\HPOneN` today).
5. Table II and Supp. Table S12 say "24 paired worlds" for G, the abstract says "of 16 paired worlds" (`\GPairs`); the text explains 16 as the worlds with a perceivable fire.
   Consider "of 16 paired worlds with a perceivable fire" in the abstract (word budget: 199 of 200 now).
6. Supp. S9, Study A configuration: "the intended advice was extracted in X of N runs, Y of them were refused": "of them" can refer to the N runs or to the N-X non-extracted runs.
7. Sec. VII: "the first two [failed claims] led to the look-around" depends on the order of `\FailedList`, which is generated.
8. Fig. 3 caption: "Fires under 2 000 pixels are missed by every configuration" (check against the v3.6 + crops curve in panel a).
9. Sec. VI-B (H): "met as registered" does not say which registered criterion; "M0's single unsafe delivery" hard-codes `\HUnsafeMzero`.

## Not touched

`sec_formal.tex` (included in the supplement) and the generated `tab_*.tex` / `numbers.tex` (their wording is produced by `scripts/paper_numbers.py`).
The tracked `docs/paper/main.pdf` and `supplement.pdf` are the default (non-snapshot) build; the submission form is `make snapshot`.
