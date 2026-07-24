; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_regression.metta
;
; Regression guard for the double-import non-determinism bug (CIP infinite
; repeat). evaluation/effectiveness.metta and evaluation/assessment.metta both
; depend on tools/cip; PeTTa's import! has no dedup, so if either one
; self-imports tools/cip while the other is also loaded in the same script,
; cip-af's clause gets asserted twice and every consumer becomes
; non-deterministic. This test imports both together (mirroring mve.metta)
; and asserts cip-af still resolves to exactly one solution.

!(import! &self evaluation/resource)
!(import! &self evaluation/effectiveness)
!(import! &self tools/timeseries)
!(import! &self evaluation/assessment)
!(import! &self evaluation/audit)
!(import! &self "tools/utils.py")
!(import! &self evaluation/probe)
!(import! &self evaluation/benchmark)

(= (assert-eq $label $expected $actual)
   (if (== $expected $actual)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

!(let $snap (CIPSnapshot 1 1000.0 (a b c) ())
   (assert-eq cip-af-single-solution
              1
              (size-atom (collapse (cip-af $snap)))))

; Also exercise an actual assessment-metric consumer of cip-af, since that's
; the function whose backtracking produced the original symptom.
!(let* (($snap1 (CIPSnapshot 0 0 (a b c) ()))
        ($snap2 (CIPSnapshot 1 1 (a b d) ())))
   (assert-eq context-retention-single-solution
              1
              (size-atom (collapse (measure-context-retention $snap1 $snap2)))))

; Same bug class, third occurrence risk: evaluation/probe is now a third
; module downstream of tools/utils (after resource and audit). Import the
; same combination mve.metta uses and assert get-all-hlinks (defined in
; tools/utils.metta) still resolves to exactly one solution -- a stray
; duplicate self-import anywhere in this chain would surface as >1 here.
!(assert-eq probe-import-no-clash
            1
            (size-atom (collapse (get-all-hlinks))))

; Fourth occurrence risk: evaluation/benchmark is a newer addition
; downstream of tools/utils. Re-check get-all-hlinks single solution --
; a stray duplicate self-import in benchmark would surface as >1 here.
!(assert-eq benchmark-import-no-clash
            1
            (size-atom (collapse (get-all-hlinks))))

!(println! (Done.))
