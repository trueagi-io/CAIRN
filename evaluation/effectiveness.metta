; =============================================================
; CAIRN – Effectiveness Calculation  (spec §2.2)
;
; Quantifies attention effectiveness as performance gain per
; resource unit across two CIP snapshots.
;
; Depends on: tools/cip (CIPSnapshot, Metric, get-metric)
;             resource.metta (measure-af-size-ratio,
;                             measure-sti-concentration,
;                             measure-link-density)
;             metta-attention API (getAfAtoms, stimulate)
; =============================================================

!(import! &self tools/cip)
; NOTE: effectiveness.metta is the designated sole self-importer of tools/cip
; in the mve.metta/demo.metta load chain. Downstream modules must NOT
; self-import it — doing so duplicates Prolog clauses (PeTTa has no import
; dedup), causing silent non-determinism. See dev-tests/test_regression.metta.
; resource.metta must be imported by the caller before this file.
; PeTTa cannot resolve bare module names (without '/') from within evaluation/.

; ---- §2.2.1  Snapshot helpers --------------------------------

; Capture the current ECAN state into a CIPSnapshot.
; Records sti-concentration and link-density as named Metrics
; so aggregate-metric-delta can compare two snapshots by name.
(= (snapshot-now $index)
   (let* (($af    (getAfAtoms))
          ($ts    (current-time))
          ($sti-c (measure-sti-concentration))
          ($l-d   (measure-link-density)))
        (CIPSnapshot $index $ts $af
                     (cons (Metric sti-concentration $sti-c)
                           (cons (Metric link-density $l-d) ())))))

; Advance to the next CIP by capturing a fresh snapshot.
(= (transition-to-next-cip $prev-cip)
   (let* (($i    (cip-index $prev-cip))
          ($next (+ $i 1)))
        (snapshot-now $next)))

; ---- §2.2.2  Metric delta ------------------------------------

; Average improvement across STI-concentration and link-density.
; Positive means attention state improved between snapshots.
(= (aggregate-metric-delta $s1 $s2)
   (let* (($c1     (get-metric $s1 sti-concentration))
          ($c2     (get-metric $s2 sti-concentration))
          ($d1     (get-metric $s1 link-density))
          ($d2     (get-metric $s2 link-density))
          ($d-conc (- $c2 $c1))
          ($d-dens (- $d2 $d1)))
        (/ (+ $d-conc $d-dens) 2.0)))

; ---- §2.2.3  Resource cost -----------------------------------

; Combined resource footprint: AF occupancy + STI concentration + link
; overhead (spec §2.1's three resource-cost factors). All three are
; normalised to [0, 1] by resource.metta.
(= (total-resource-cost)
   (let* (($r (measure-af-size-ratio))
          ($c (measure-sti-concentration))
          ($d (measure-link-density)))
        (+ $r (+ $c $d))))

; ---- §2.2.4  Effectiveness -----------------------------------
; Δperf = mean(sti-concentration, link-density) change (CAIRN bag).
; Primary reported effectiveness is global (baseline → current).

(= (calculate-effectiveness $from $to)
   (let* (($perf-delta    (aggregate-metric-delta $from $to))
          ($resource-cost (total-resource-cost)))
        (if (> $resource-cost 0.0)
            (/ $perf-delta $resource-cost)
            0.0)))

(= (measure-local-effectiveness $prev $curr)
   (calculate-effectiveness $prev $curr))

(= (measure-global-effectiveness $baseline $curr)
   (calculate-effectiveness $baseline $curr))

; ---- §2.2.5  Redundancy Degradation Test ---------------------

; Add a cons-list of atoms to ECAN by stimulating each one.
; stimulate $atom $stimulus increments the atom's STI by a
; wage-scaled amount (metta-attention attention-bank API).
(= (add-redundant-atoms () $_) done)
(= (add-redundant-atoms (cons $atom $rest) $stimulus)
   (let* (($_ (stimulate $atom $stimulus)))
        (add-redundant-atoms $rest $stimulus)))

; Measure how much inserting redundant atoms degrades attention
; efficiency.  $redundant-copies: cons-list of atom names.
; Returns (PerformanceReport redundancy-impact $degradation-rate).
(= (test-redundancy-degradation $cip-prev $cip-curr $redundant-copies)
   (let* (($baseline-perf  (aggregate-metric-delta $cip-prev $cip-curr))
          ($baseline-cost  (total-resource-cost))
          ($_ (add-redundant-atoms $redundant-copies 1.0))
          ($degraded-cip   (transition-to-next-cip $cip-curr))
          ($degraded-perf  (aggregate-metric-delta $cip-prev $degraded-cip))
          ($new-cost       (total-resource-cost))
          ($overhead       (- $new-cost $baseline-cost))
          ($degradation-rate
               (if (> $overhead 0.0)
                   (/ (- $baseline-perf $degraded-perf) $overhead)
                   0.0)))
        (PerformanceReport redundancy-impact $degradation-rate)))
