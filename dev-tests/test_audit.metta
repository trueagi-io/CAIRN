; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_audit.metta
; Tests for evaluation/audit.metta with stubbed metta-attention API.

(= (getAtomsInTypeSpace) (a b c d))

!(import! &self tools/utils)
!(import! &self evaluation/audit)

(= (assert-approx $label $expected $actual $tol)
   (if (< (abs-val (- $expected $actual)) $tol)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

(= (abs-val $x) (if (< $x 0.0) (- 0.0 $x) $x))

; STI 1,2,3,4 -> shifted 0,1,2,3 -> dist 0,1/6,2/6,3/6
; entropy = -(1/6 log2 1/6 + 2/6 log2 2/6 + 3/6 log2 3/6) ~= 1.45915 bits
; normalized by log2(4) = 2 -> ~0.72957
(= (getSti a) 1.0)
(= (getSti b) 2.0)
(= (getSti c) 3.0)
(= (getSti d) 4.0)
!(assert-approx preallocation-space-varied 0.7296
    (measure-preallocation-space) 0.01)

!(println! (Done.))
