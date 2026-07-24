; =============================================================
; CAIRN – Benchmark Metric  (spec §2.2, Phase VIII)
;
; Compares the effectiveness of two ECAN runs (baseline vs
; optimized) over paired consecutive CIP snapshots.
;
; Depends on: evaluation/effectiveness (calculate-effectiveness)
;             -- caller must pre-import this; this file must NOT
;             self-import tools/utils (double-import rule --
;             see evaluation/resource.metta, test_regression.metta).
; =============================================================

; ---- §2.2  Gained Efficiency --------------------------------
; Normalized effectiveness improvement of the optimized run
; relative to the baseline.  Returns 0.0 when the baseline
; effectiveness is zero (avoids division by zero).

(= (measure-gained-efficiency $base-prev $base-curr $opt-prev $opt-curr)
   (let* (($baseline-eff  (calculate-effectiveness $base-prev $base-curr))
          ($optimized-eff (calculate-effectiveness $opt-prev  $opt-curr)))
      (measure-gained-efficiency-from-eff $baseline-eff $optimized-eff)))

; abs-math on the denominator (not $baseline-eff directly) keeps the
; sign of the result meaningful when the baseline is negative -- e.g.
; baseline=-2, optimized=-1 is an improvement and should read positive.
(= (measure-gained-efficiency-from-eff $baseline-eff $optimized-eff)
   (let $abs-baseline (abs-math $baseline-eff)
      (if (== $abs-baseline 0.0)
          0.0
          (/ (- $optimized-eff $baseline-eff) $abs-baseline))))
