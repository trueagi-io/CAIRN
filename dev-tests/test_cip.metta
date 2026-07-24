; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_cip.metta

!(import! &self tools/cip)

(= (assert-eq $label $expected $actual)
   (if (== $expected $actual)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

!(let $metrics (cons (Metric af-size-ratio 0.5)
                (cons (Metric sti-concentration 0.72)
                      ()))
   (let $snap (CIPSnapshot 3 1000.0 (a b c) $metrics)
        (let* (($_ (assert-eq cip-index       3       (cip-index $snap)))
               ($_ (assert-eq cip-timestamp   1000.0  (cip-timestamp $snap)))
               ($_ (assert-eq cip-af          (a b c) (cip-af $snap)))
               ($_ (assert-eq get-metric-hit  0.5     (get-metric $snap af-size-ratio)))
               ($_ (assert-eq get-metric-hit2 0.72    (get-metric $snap sti-concentration)))
               ($_ (assert-eq get-metric-miss 0.0     (get-metric $snap link-density))))
             done)))
