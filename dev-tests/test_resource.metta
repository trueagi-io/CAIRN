; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_resource.metta
; Tests for evaluation/resource.metta with stubbed metta-attention API.
;
; Scenario:
;   Atoms in typeSpace: a b c d  (4 total)
;   AF members:        a b c    (3 members)
;   STI:               a=0.5  b=0.3  c=0.2  d=0.0
;   HebbianLinks:      a→b  a→c  b→c  (all within AF)
;
; Expected:
;   af-size-ratio     = 3.0 / 4.0        = 0.75
;   sti-concentration = (0.5+0.3+0.2) / (0.5+0.3+0.2+0.0) = 1.0
;   link-density      = 3.0 / (3.0*2.0) = 0.5

; ---- Stub metta-attention API --------------------------------

!(bind! &typeSpace (new-space))

!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a b) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a c) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK b c) stub))

(= (getAfAtoms)        (a b c))
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
; resource.metta imports ../tools/utils internally;
; importing it here too would duplicate every clause.

!(import! &self evaluation/resource)

; ---- Helpers -------------------------------------------------

(= (assert-approx $label $expected $actual $tol)
   (let* (($diff (- $expected $actual))
          ($abs  (if (< $diff 0.0) (- 0.0 $diff) $diff))
          ($ok   (< $abs $tol)))
        (if $ok
            (println! (PASS $label))
            (println! (FAIL $label expected: $expected got: $actual)))))

; ---- Tests ---------------------------------------------------

!(let $r (measure-af-size-ratio)
   (assert-approx af-size-ratio 0.75 $r 0.001))

!(let $c (measure-sti-concentration)
   (assert-approx sti-concentration 1.0 $c 0.001))

!(let $d (measure-link-density)
   (assert-approx link-density 0.5 $d 0.001))
