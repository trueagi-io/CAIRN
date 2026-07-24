; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_assessment.metta
; Tests for evaluation/assessment.metta with stubbed metta-attention API.
;
; Scenario:
;   Atoms in typeSpace: a b c d  (4 total)
;   AF members:        a b c    (3 members)
;   STI:               a=0.5  b=0.3  c=0.2  d=0.0
;   LTI:               a=0.9  b=0.6  c=0.3  d=0.0
;   HebbianLinks:      a→b  a→c  b→c  (all within AF)
;   Link probabilities: a→b=0.8  a→c=0.6  b→c=0.7

; ---- Stub metta-attention API --------------------------------

!(bind! &typeSpace (new-space))

!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a b) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a c) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK b c) stub))

(= (getAfAtoms)          (a b c))
(= (getAtomsInTypeSpace) (a b c d))

(= (getSti a) 0.5)
(= (getSti b) 0.3)
(= (getSti c) 0.2)
(= (getSti d) 0.0)

(= (getLti a) 0.9)
(= (getLti b) 0.6)
(= (getLti c) 0.3)
(= (getLti d) 0.0)

(= (getMean (ASYMMETRIC_HEBBIAN_LINK a b)) 0.8)
(= (getMean (ASYMMETRIC_HEBBIAN_LINK a c)) 0.6)
(= (getMean (ASYMMETRIC_HEBBIAN_LINK b c)) 0.7)

(= (isAtomInAf a) True)
(= (isAtomInAf b) True)
(= (isAtomInAf c) True)
(= (isAtomInAf d) False)

; ---- Stub time-series data -----------------------------------

!(bind! &stub-sti (new-space))
!(bind! &stub-lti (new-space))

!(add-atom &stub-sti (sti a 8.0))
!(add-atom &stub-sti (sti b 3.0))
!(add-atom &stub-lti (lti a 0.9))
!(add-atom &stub-lti (lti b 0.4))

; ---- Load modules under test ---------------------------------

!(import! &self evaluation/resource)
!(import! &self tools/timeseries)
!(import! &self tools/cip)
!(import! &self evaluation/assessment)

!(record-cip-series)

; ---- Helpers -------------------------------------------------

(= (assert-approx $label $expected $actual $tol)
   (if (< (abs-val (- $expected $actual)) $tol)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

(= (abs-val $x) (if (< $x 0.0) (- 0.0 $x) $x))

; ---- Tests ---------------------------------------------------

!(println! (=== Assessment Tests ===))

; Context retention: Jaccard similarity with same AF = 1.0
!(let* (($snap1 (CIPSnapshot 0 0 (a b c) ()))
        ($snap2 (CIPSnapshot 1 1 (a b c) ())))
    (assert-approx context-retention-same 1.0
        (measure-context-retention $snap1 $snap2) 0.01))

; Context retention: partial overlap
!(let* (($snap1 (CIPSnapshot 0 0 (a b c) ()))
        ($snap2 (CIPSnapshot 1 1 (a b d) ())))
    (assert-approx context-retention-partial 0.5
        (measure-context-retention $snap1 $snap2) 0.01))

; Selective modulation: should be > 0 with non-uniform STI
!(let $sel (measure-selective-modulation)
    (if (> $sel 0.0)
        (println! (PASS selective-modulation-positive))
        (println! (FAIL selective-modulation-positive got: $sel))))

; Connection ratio: 3 AF-out links, all targets in AF
!(assert-approx connection-ratio 1.0
    (measure-connection-ratio) 0.01)

!(let $di (measure-distributed-importance)
    (println! (distributed-importance: $di)))

; Attention coherence: should return a number
!(let $coh (measure-attention-coherence)
    (println! (attention-coherence: $coh)))

!(println! (Done.))
