; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_benchmark.metta
; Tests for evaluation/benchmark.metta.
;
; Stubs calculate-effectiveness locally so evaluation/effectiveness
; is not imported — this avoids tools/cip entering the load chain
; (which would require tools/cip to be pre-imported by a designated
; module, per the double-import rule in test_regression.metta).

; ---- Stub calculate-effectiveness with controllable test values ----
; Each snapshot atom encodes its effectiveness: baseline-prev/curr
; give 0.5, optimized-prev/curr give 1.0.

(= (calculate-effectiveness base-prev base-curr) 0.5)
(= (calculate-effectiveness opt-prev  opt-curr)  1.0)
(= (calculate-effectiveness zero-prev zero-curr) 0.0)
(= (calculate-effectiveness reg-prev  reg-curr)  0.5)
(= (calculate-effectiveness reg-opt-prev reg-opt-curr) 0.25)
(= (calculate-effectiveness negbase-prev negbase-curr) -2.0)
(= (calculate-effectiveness negopt-prev  negopt-curr)  -1.0)

!(import! &self evaluation/benchmark)

(= (assert-approx $label $expected $actual $tol)
   (if (< (abs-val (- $expected $actual)) $tol)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

(= (abs-val $x) (if (< $x 0.0) (- 0.0 $x) $x))

; Case 1: 100 % gain (baseline_eff=0.5, optimized_eff=1.0)
; expected: (1.0 - 0.5) / 0.5 = 1.0
!(assert-approx benchmark-100pct-gain 1.0
    (measure-gained-efficiency base-prev base-curr opt-prev opt-curr) 0.001)

; Case 2: 50 % regression (baseline_eff=0.5, optimized_eff=0.25)
; expected: (0.25 - 0.5) / 0.5 = -0.5
!(assert-approx benchmark-50pct-regression -0.5
    (measure-gained-efficiency reg-prev reg-curr reg-opt-prev reg-opt-curr) 0.001)

; Case 3: zero-baseline guard (baseline_eff=0.0)
; expected: 0.0 (no division by zero)
!(assert-approx benchmark-zero-baseline 0.0
    (measure-gained-efficiency zero-prev zero-curr opt-prev opt-curr) 0.001)

; Case 4: negative-baseline sign (baseline_eff=-2.0, optimized_eff=-1.0)
; an improvement (less negative) must read as a positive gain, not negative
; expected: (-1.0 - -2.0) / abs(-2.0) = 1.0 / 2.0 = 0.5
!(assert-approx benchmark-negative-baseline-improvement 0.5
    (measure-gained-efficiency negbase-prev negbase-curr negopt-prev negopt-curr) 0.001)

!(println! (Done.))
