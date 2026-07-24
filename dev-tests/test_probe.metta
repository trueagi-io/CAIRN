; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_probe.metta
; Tests for evaluation/probe.metta.
; measure-glocal-coordination's full composition (also needs
; getMean/STV and &sti-series stubs) is left for mve.metta
; integration testing -- see dev-tests/test_homology.metta's
; identical precedent for persistent-homology-invariants.

; ---- Load modules under test ----------------------------------

!(import! &self tools/utils)
!(import! &self tools/cip)
!(import! &self evaluation/assessment)
!(import! &self "../tools/utils.py")
!(import! &self evaluation/probe)

; ---- Helpers -------------------------------------------------

(= (assert-eq $label $expected $actual)
   (if (== $expected $actual)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

(= (assert-approx $label $expected $actual $tol)
   (if (< (abs-val (- $expected $actual)) $tol)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

(= (abs-val $x) (if (< $x 0.0) (- 0.0 $x) $x))

; ---- identify-modules round-trip (py-call list-of-atoms risk) --
; Two disjoint triangles -> 2 modules, atom identity preserved.

!(bind! &typeSpace (new-space))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a b) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK b c) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a c) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK x y) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK y z) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK x z) stub))

(= (getMean $link) 0.5)

!(let $modules (identify-modules (get-all-hlinks))
   (assert-eq identify-modules-two-triangles 2 (size-atom $modules)))

; Atom 'a' must structurally match inside whichever module contains it.
!(let $modules (identify-modules (get-all-hlinks))
   (let $idx (module-index-of a $modules 0)
      (assert-eq identify-modules-atom-roundtrip True (>= $idx 0))))

; ---- measure-cognitive-maintenance ------------------------------
; AF sets: (a b c) -> (a b d) -> (a b d e)
; Jaccard(1,2) = |{a,b}| / |{a,b,c,d}| = 2/4 = 0.5
; Jaccard(2,3) = |{a,b,d}| / |{a,b,d,e}| = 3/4 = 0.75
; average = 0.625

!(let* (($s1     (CIPSnapshot 0 0.0 (a b c) ()))
        ($s2     (CIPSnapshot 1 1.0 (a b d) ()))
        ($s3     (CIPSnapshot 2 2.0 (a b d e) ()))
        ($series (cons $s1 (cons $s2 (cons $s3 ())))))
   (assert-approx cognitive-maintenance-trajectory 0.625
      (measure-cognitive-maintenance $series) 0.001))

!(println! (Done.))
