; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_effectiveness.metta
; Tests for evaluation/effectiveness.metta with stubbed metta-attention API.
;
; Scenario (same as test_resource.metta):
;   Atoms in typeSpace: a b c d  (4 total)
;   AF members:        a b c    (3 members)
;   STI:               a=0.5  b=0.3  c=0.2  d=0.0
;   HebbianLinks:      a→b  a→c  b→c  (all within AF)
;
; Derived values from resource.metta:
;   af-size-ratio     = 0.75
;   sti-concentration = 1.0
;   link-density      = 0.5
;   total-resource-cost = 0.75 + 1.0 + 0.5 = 2.25

; ---- Stub metta-attention API --------------------------------

!(bind! &typeSpace (new-space))

!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a b) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a c) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK b c) stub))

(= (getAfAtoms)          (a b c))
(= (getAtomsInTypeSpace) (a b c d))
(= (getAllAtomsWithBins) (a b c d))
(= (countAtomsInTypeSpace) 4)

(= (getSti a) 0.5)
(= (getSti b) 0.3)
(= (getSti c) 0.2)
(= (getSti d) 0.0)

(= (isAtomInAf a) True)
(= (isAtomInAf b) True)
(= (isAtomInAf c) True)
(= (isAtomInAf d) False)

; ---- Load module under test ----------------------------------
; Import resource FIRST so its Prolog predicates are in the DB
; when effectiveness.metta's function bodies are compiled.
; PeTTa cannot resolve a bare 'resource' path from within evaluation/,
; so effectiveness.metta itself cannot import it — the caller must.
; effectiveness.metta imports ../tools/cip; do NOT import it here (Rule 5).

!(import! &self evaluation/resource)
!(import! &self evaluation/effectiveness)

; ---- Helpers -------------------------------------------------

(= (assert-eq $label $expected $actual)
   (if (== $expected $actual)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

(= (assert-approx $label $expected $actual $tol)
   (let* (($diff (- $expected $actual))
          ($abs  (if (< $diff 0.0) (- 0.0 $diff) $diff))
          ($ok   (< $abs $tol)))
        (if $ok
            (println! (PASS $label))
            (println! (FAIL $label expected: $expected got: $actual)))))

; ---- Test 1: total-resource-cost = 0.75 + 1.0 + 0.5 = 2.25 --

!(let $cost (total-resource-cost)
   (assert-approx total-resource-cost 2.25 $cost 0.001))

; ---- Test 2: snapshot-now builds correct CIPSnapshot ---------
; Verifies that snapshot-now stores metric values retrievable by name.

!(let* (($snap (snapshot-now 0))
        ($idx  (cip-index $snap))
        ($conc (get-metric $snap sti-concentration))
        ($dens (get-metric $snap link-density)))
   (let* (($_ (assert-eq   snapshot-index 0   $idx))
          ($_ (assert-approx snapshot-conc 1.0 $conc 0.001))
          ($_ (assert-approx snapshot-dens 0.5 $dens 0.001)))
         done))

; ---- Test 3: transition-to-next-cip increments index ---------

!(let* (($s0  (snapshot-now 0))
        ($s1  (transition-to-next-cip $s0))
        ($idx (cip-index $s1)))
   (assert-eq transition-index 1 $idx))

; ---- Test 4: aggregate-metric-delta --------------------------
; Construct two snapshots directly (bypasses snapshot-now) so
; metric values are decoupled from the live stub state.
;
; baseline: sti-conc=0.5, link-density=0.3
; current:  sti-conc=0.7, link-density=0.5
; expected delta = ((0.7-0.5) + (0.5-0.3)) / 2.0 = 0.2

!(let* (($base  (CIPSnapshot 0 0.0 (a b)
                   (cons (Metric sti-concentration 0.5)
                         (cons (Metric link-density 0.3) ()))))
        ($curr  (CIPSnapshot 1 0.0 (a b c)
                   (cons (Metric sti-concentration 0.7)
                         (cons (Metric link-density 0.5) ()))))
        ($delta (aggregate-metric-delta $base $curr)))
   (assert-approx aggregate-metric-delta 0.2 $delta 0.001))

; ---- Test 5: calculate-effectiveness -------------------------
; effectiveness = aggregate-delta / total-resource-cost
;               = 0.2 / 2.25 = 0.0889
; (resource-cost is computed live from the stub, not from snapshots)

!(let* (($base  (CIPSnapshot 0 0.0 (a b)
                   (cons (Metric sti-concentration 0.5)
                         (cons (Metric link-density 0.3) ()))))
        ($curr  (CIPSnapshot 1 0.0 (a b c)
                   (cons (Metric sti-concentration 0.7)
                         (cons (Metric link-density 0.5) ()))))
        ($eff   (calculate-effectiveness $base $curr)))
   (assert-approx calculate-effectiveness 0.0889 $eff 0.001))

; test-redundancy-degradation requires live stimulate API — integration test
