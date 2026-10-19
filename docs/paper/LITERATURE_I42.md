# Novelty check for I-42 (continue after a real hazard refusal) -- 2026-10-19

Method: 6 web searches (3 standard, 4 extended; terms: tighten-only / attenuation-only advice + availability, denial of service of safety gates, continue / fallback after refusal, learning-augmented robustness-consistency, Simplex runtime assurance liveness) and 3 abstract fetches. The search engine returns what it indexes; this is a check, not a proof that nothing exists.

## What was found (nearest neighbours)
| Work | What it does | Difference from I-42 |
|---|---|---|
| Physical Agentic AI (arXiv 2608.22657, Aug 2026) | deterministic orchestrator refuses a faulty step before motion (8/8 refused, 0 false blocks on its tests) | what happens after the refusal is not described (refuse and report); no untrusted advice channel; no availability analysis |
| Semantic DoS in LLM-controlled robots (2604.24790) | injected audio text halts a robot; 7 prompt-level defences trade attack suppression against real-hazard response (DSR) | measured qualitatively on prompts; no formal guarantee; fix called architectural |
| SafeGate (2604.05427) | authorize / defer / reject before execution; false-block rate counted | gate on commands, not on advice; no continuation across candidates; no proof of availability |
| Black-box Simplex (2102.12981) and verified Simplex | switch from the untrusted advanced controller to a trusted baseline when the monitor sees danger | the structural analogue: the fallback keeps the system live; ours is a search over candidate bays with a perception gate, and advice (not a controller) is the untrusted input; no statement "loses a delivery only if every approving bay was tightened" |
| Learning-augmented algorithms (2010.11443 etc.) | consistency / robustness trade-off for untrusted predictions | competitive ratios of online algorithms, not a perception gate; already in LITERATURE_I24 |
| Guardrails as Scapegoats (2607.19449) | unfaithful safety refusals of LLM agents | different object (tool failures) |

## Reading
* No work found that (a) admits only tighten-only advice, (b) proves with an SMT solver that continuing past a refusal keeps the per-station safety rule, and (c) gives and measures an availability statement ("advice loses a delivery only if every station that approves without advice was tightened"). Closest in spirit: Simplex (fallback keeps liveness) and the semantic-DoS paper (availability attack, no guarantee).
* The mechanism (try the next candidate after a refusal) is ordinary; the claim of novelty rests on the proof, the stated limit (A1: visit order, exposure) and the registered measurement (study Y), not on the flag. The paper says so.
* To cite: 2608.22657 and 2604.24790 as availability-side neighbours (one sentence each); Simplex as the structural analogue (already cited as Mehmood et al.).
