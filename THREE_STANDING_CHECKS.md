# THREE STANDING CHECKS

**Each guards a demonstrated failure mode. All three live OUTSIDE the audit
loop's native competence: the loop checks whether a computation is CORRECT,
and none of these three is about correctness of a computation in isolation.**

---

## 1. WRONG VALUE — a computation is arithmetically wrong.

**Defense:** The audit loop (already in place). Re-run, cross-check arithmetic.

**Status:** Covered.

---

## 2. WRONG BINDING — a correct object placed in the wrong role.

Right value, wrong referent. Examples: class 9 vs cl11 (valid class, order 6
not 2); G∘G vs G(x³+x) (both degree 9, both typecheck); one symbol "ε_p" for
three quantities (cp_p, LL_p, bp).

**Defense: BINDING-TYPE-CHECK.** At each named-object identification, assert
its defining type constraint:
  - Involution → order 2.
  - Ordinary prime → splits in CM field.
  - Defect group → right p-part order.
  - Frobenius class → cycle type matches PARI factorization UNIQUELY.
  - Conjugacy class → UNIQUE among same-order same-cycle-type classes.
  - **Block assignment → from GAP PrimeBlocks/BrauerTable, NEVER inferred
    from the rational character table.** The S₃ block error (principal={triv,sgn},
    not {triv,std}) was caused by reasoning from the rational table. The modular
    table and the rational table give different block assignments when p | dim(ρ).
    (Second mathematician, 2026-05-28.)
    **GAP-VERIFIED (VR-595, iter 542):** `PrimeBlocks(ct, 2)` confirms
    principal={triv,sgn} (defect 1), defect-0={std}. All FS=1 (orthogonal).
    sha_std=16 at 57 digits via lfundiv (VR-595). Block correction is RIGHT.

Bind to a canonical computed-from-scratch source; import, never recompute inline.

**PRECONDITION (external review, 2026-05-25):** A canonical class identification
file must EXIST at each level before any computation that identifies classes at
that level. The wrong-binding failure mode appeared at BOTH k=2 (VR-241→300,
pre-318 era) and k=3 (cl9→cl11, Sonnet era). It is ENDEMIC, not level-specific
or model-specific. The defense must precede the error, not follow it.
  k=2: results/k2_class_identifications.json (CREATED VR-529; τ₇=cl3 added VR-530).
  k=3: results/k3_class_identifications.json (created VR-506).
  k=4: must be created BEFORE any k=4 class computation begins.

The loop is blind here because each computation typechecks in isolation — the
error is in the naming.

---

## 3. UNNECESSARY COMPUTATION — elaborate work on a structurally trivial quantity.

Example: 115 VRs computing odd-p local factors that good reduction (conductor
2⁶) forces to +1 at k=2. The structural bound existed from VR-318.

**Defense: TRIVIALITY CHECK.** Before elaborate computation, state the structural
bound (conductor, ramification, parity, defect) that fixes or bounds the quantity.
Compute only what the bound leaves free. When computation contradicts the bound,
suspect the computation, not the structural bound, because the structural bound
has fewer moving parts.

**REFINEMENT (external review, 2026-05-25, post VR-521→528 overclaim):**
A triviality argument has TWO PARTS:
  (a) The STRUCTURAL MECHANISM (transfers across levels/cases for free).
  (b) The COMPUTATIONAL STEP that turns the mechanism into a specific value.
Only part (a) generalizes. Part (b) is valid only where performed.

When stating a triviality bound, MARK which part is structural and which is
a computation valid only at the current level. The bound does NOT generalize
until the computational step is re-performed at the new level.

Example (VR-521):
  (a) Good reduction → GF(2) constraints. STRUCTURAL, all k. ✓
  (b) Constraints → unique trivial solution. COMPUTATIONAL, requires full GF(2)
      rank, which was computed at k=2 (rank 22 = 22 irreps) but is FALSE at k=3
      (rank < 2530, 256 irreps carry nontrivial odd-p content).
The all-k claim smuggled part (b) along with part (a).

**Sub-clause:** "Does the VALUE follow from the structural fact alone, or from
the structural fact PLUS a computed quantity (a rank, a count, a factorization)
that is itself level-specific?" If the latter: the value does not generalize
until the computed quantity is recomputed at the new level.

**Affective signal:** "This finally makes everything simple" / relief after a
long struggle → trigger for MORE scrutiny, not less. Relief is the affective
signature of an overclaim about to happen. (Both the second-order recursion
and VR-521 were emotionally satisfying simplifications that turned out wrong.)

---

## CROSS-CUTTING PRINCIPLES (apply across all three)

- **By-construction relations prove nothing.** X := Y/Z makes X·Z = Y vacuous.
  Confirmation needs an INDEPENDENT route, never the relation it was built to
  satisfy, never a derived consequence.

- **A check that passes under both wrong and corrected inputs does not constrain
  those inputs.** (36/36 passed under both 400 and 128.) Identify what it
  actually constrains.

- **Coincidence at low levels is not evidence.** (G, τ, R all = 3 at k=2.)
  Name where quantities first DISAGREE and check there.

- **Count free parameters.** Independent checks must exceed them. Report
  framework-DETERMINED quantities separately from computed ones. Determined
  quantities never count as confirmations.

- **Provenance lowers the prior broadly.** When a source is found less reliable,
  distrust its type-CORRECT identifications too, not only the ones that violated
  a constraint and got caught.

- **Same count is not same set.** A formula that reproduces a number (e.g., 256)
  is the START of a check, not the end. The independent route is whether the
  SAME ELEMENTS are identified by the structural mechanism as by the count.
  Clean powers of 2 at k=3 are yellow flags (400→384→128, 128=2⁷, 256=2⁸).

- **Formula transcription is failure mode 1 wearing a different costume.**
  A formula verified in one script (VR-129) and transcribed to another (VR-543)
  dropped two factors (2^{r₂} and c_∞^{r₁}). The transcribed formula produced
  plausible Sha values (small powers of 2) that generated 16 VRs of false
  narrative (abelian dichotomy, A₄ confirmation, S₃ anomaly). Defense:
  canonical scripts imported, never transcribed. A baseline check (Sha=1 for
  E/ℚ) catches transcription errors before they propagate.

- **"What cancels?" before computing.** If a quantity X appears with equal
  weight in numerator and denominator: let it cancel rather than computing it.
  The period cancels in lfun/ellbsd (three corrections avoided if we'd started
  here). Induced representations cancel against base-field computations (Artin
  formalism). The val₂+defect constant is conserved across the tower.
  "Before computing X, ask what X cancels against" — the structural shortcut
  that bypasses entire error classes. (External mathematician, 2026-05-27.)

- **Do not build arguments on unverified corrections.** A correction to a
  value or structure (block assignment, class identification, period formula)
  is itself unverified until GAP/PARI confirms it. Building a theoretical
  reorientation on a correction that hasn't been machine-checked is the same
  failure mode as building on the original wrong value: clean-looking argument,
  unverified foundation. The d=-31 "category error proof" used the S₃ block
  correction (principal={triv,sgn}) before GAP confirmed it, AND used
  sha_std=16 before high-precision re-extraction. Both arguments that touched
  d=-31 (the ε-from-Sha refutation AND the defect-0 anomaly) were suspended
  by this discipline. Verify the correction FIRST, then build on it.
  (Second mathematician, 2026-05-28.)

---

## PROOF-STATUS LEDGER (maintain per claim, never let drift)

| Status | Meaning |
|--------|---------|
| **PROVED** | Independent derivation, ideally >1 method. |
| **VERIFIED** | Checked against data / computation. |
| **RECOMPUTED-PENDING-INDEPENDENT-CHECK** | Recomputed more carefully but not independently confirmed. |
| **DERIVED-FROM-FRAMEWORK** | Determined by the framework's own assumptions. Cannot count as confirmation of the framework. |
