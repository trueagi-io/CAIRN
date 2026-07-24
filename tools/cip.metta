; ---- Metric record ------------------------------------------
; (Metric <name-symbol> <value-number>)
(: Metric Type)

; ---- CIPSnapshot --------------------------------------------
; (CIPSnapshot $index $timestamp $af $metrics)
;   $index     : Number      – 0 = baseline
;   $timestamp : Number      – unix time at capture
;   $af        : Expression  – frozen result of getAfAtoms
;   $metrics   : List Metric – cons list of (Metric name value)
(: CIPSnapshot Type)
(= (cip-index     (CIPSnapshot $i $_ $_ $_)) $i)
(= (cip-timestamp (CIPSnapshot $_ $t $_ $_)) $t)
(= (cip-af        (CIPSnapshot $_ $_ $a $_)) $a)
(= (cip-metrics   (CIPSnapshot $_ $_ $_ $m)) $m)

; Look up a named metric in a snapshot. Returns 0.0 if absent.
(= (get-metric $snap $name) (find-metric (cip-metrics $snap) $name))
(= (find-metric () $_) 0.0)
(= (find-metric (cons (Metric $n $v) $rest) $name)
   (if (== $n $name) $v (find-metric $rest $name)))

; ---- PerformanceReport ----------------------------------------
; (PerformanceReport $label $value)

(: PerformanceReport Type)