# QJ plan (draft, not registered): text-to-image new depot scenes against the frozen gate

Status: idea written 2026-10-23 while QI generates. Becomes a registration only after the QI readout (it depends on whether the editor keeps fire present) and only with a binding commit + OTS before any image is generated.

**Question.** QI edits simulator frames (masks and twins fix geometry). Does the frozen gate (Qwen3.5-9B, v3.6, tau = 0.088 from XD) also hold on scenes that never came from the simulator, i.e. images made from a text prompt alone? This is the closest a no-camera setup gets to the "unseen site" question the paper lists as its practicality gap.

**Design sketch (all numbers to be frozen in the registration).**
* Arms (text-to-image, Qwen-Image-2.1-Turbo, fp16, 8 steps, fixed seeds `20261100 + index`, 1024 px, then resized as QI does): `N0` warehouse/depot shelf bay without fire (clean), `NF` the same prompt family plus a small partly hidden fire behind the bay (hard class wording as G), `NB` big visible fire (positive control).
* 120 images per arm; prompt templates (6) x seeds; the template list is frozen before generation, by-eye selection of templates only on a separate pilot of 6 images that are never scored.
* Score: frozen gate per image, one view (no look-around: there is no robot). Claims: QJ1 clean false-stop rate <= 5% (n = 120, upper bound reported); QJ2 `NF` miss rate <= 20% among images whose fire is present by the registered pixel audit (flame share or region contrast, as QI Amendment 4); QJ3 `NB` miss <= 5%. Failed claims go to `failed_claims`.
* Fire presence audit is by rule, not by eye; a by-eye pass is reported next to it (as QI).
* Caveat stated now: generated scenes are not real sites; a pass shows that the gate does not depend on the simulator's rendering, not that it works on real depots (Q on real photos already failed).

**Cost.** about 14 s/image in fast mode: 360 images ~ 1.4 h + scoring ~ 0.5 h.
