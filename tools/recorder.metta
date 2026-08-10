; =============================================================
; CAIRN – Result Recorder  (MeTTa wrappers for tools/recorder.py)
;
; Bridges CAIRN metric computation to Python file I/O.
; recorder.py must be imported by the caller BEFORE this file.
;
; Depends on: evaluation/resource (measure-af-size-ratio, etc.)
;             evaluation/effectiveness (calculate-effectiveness)
;             tools/homology (persistent-homology-invariants)
;             tools/timeseries (sti-trend, sti-volatility)
;             tools/utils (get-all-hlinks)
;             metta-attention API (getAfAtoms, getAttentionParam)
; =============================================================

; ---- Lifecycle -----------------------------------------------

(= (cairn-init-recorder)
   (py-call (recorder.init_recorder "output/demo")))

(= (cairn-close-recorder)
   (py-call (recorder.close_recorder)))

; ---- Per-CIP recording --------------------------------------

; Thin demo path: effectiveness = total; partial_effectiveness = step.
(= (cairn-record-cip $cip-index $baseline-snap $prev-snap $snap)
   (let* (($_ (println! (record-cip start $cip-index)))
          ($af      (getAfAtoms))
          ($af-size (size-atom $af))
          ($_ (println! (record-cip af-size $af-size)))
          ($ratio   (measure-af-size-ratio))
          ($_ (println! (record-cip af-size-ratio done)))
          ($conc    (measure-sti-concentration))
          ($_ (println! (record-cip sti-concentration done)))
          ($density (measure-link-density))
          ($_ (println! (record-cip link-density done)))
          ($eff-g   (measure-total-effectiveness $baseline-snap $snap))
          ($eff-l   (measure-partial-effectiveness $prev-snap $snap))
          ($delta   (aggregate-metric-delta $prev-snap $snap))
          ($cost    (total-resource-cost))
          ($_ (println! (record-cip effectiveness done)))
          ($topo    (persistent-homology-invariants))
          ($tri     (topology-triangles $topo))
          ($b0      (topology-betti-0 $topo))
          ($b1      (topology-betti-1 $topo))
          ($b2      (topology-betti-2 $topo))
          ($_ (println! (record-cip topology done tri $tri b0 $b0 b1 $b1 b2 $b2)))
          ($_ (py-call (recorder.record_cip
                  $cip-index $af-size
                  $ratio $conc $density
                  $eff-g $eff-l $delta $cost
                  0.0 "N/A" 0.0 0.0 0.0 0.0
                  $tri $b0 $b1 $b2))))
      (println! (record-cip written $cip-index))))

; Record metrics at a CIP boundary without deltas (baseline).
(= (cairn-record-cip-baseline $cip-index)
   (let* (($_ (println! (record-cip-baseline start $cip-index)))
          ($af      (getAfAtoms))
          ($af-size (size-atom $af))
          ($ratio   (measure-af-size-ratio))
          ($conc    (measure-sti-concentration))
          ($density (measure-link-density))
          ($_ (println! (record-cip-baseline resource done)))
          ($topo    (persistent-homology-invariants))
          ($tri     (topology-triangles $topo))
          ($b0      (topology-betti-0 $topo))
          ($b1      (topology-betti-1 $topo))
          ($b2      (topology-betti-2 $topo))
          ($_ (println! (record-cip-baseline topology done)))
          ($_ (py-call (recorder.record_cip
                  $cip-index $af-size
                  $ratio $conc $density
                  "N/A" "N/A" "N/A" "N/A"
                  0.0 "N/A" 0.0 0.0 0.0 0.0
                  $tri $b0 $b1 $b2))))
      (println! (record-cip-baseline written $cip-index))))

; ---- Final summary -------------------------------------------

(= (cairn-write-summary $params $baseline-snap $final-snap)
   (let* (($ratio   (measure-af-size-ratio))
          ($conc    (measure-sti-concentration))
          ($density (measure-link-density))
          ($topo    (persistent-homology-invariants))
          ($tri     (topology-triangles $topo))
          ($b0      (topology-betti-0 $topo))
          ($b1      (topology-betti-1 $topo))
          ($b2      (topology-betti-2 $topo))
          ($hcount  (size-atom (get-all-hlinks)))
          ($eff     (measure-total-effectiveness $baseline-snap $final-snap))
          ($trends  (cairn-collect-af-trends)))
      (py-call (recorder.write_summary
                  $params
                  ((af_size_ratio $ratio)
                   (sti_concentration $conc)
                   (link_density $density))
                  ($tri $b0 $b1 $b2 $hcount)
                  $eff
                  $trends))))

; Append whole-run probe metrics to summary.json (must be called
; after cairn-write-summary creates the file).
(= (cairn-append-probe $maintenance $glocal)
   (py-call (recorder.append_probe_metrics $maintenance $glocal)))

; Collect STI trend + volatility for current AF atoms.
; Uses getAtomsInTypeSpace pre-bound outside collapse (avoids nested
; findall -- same bug class as get-hlinks-in-af, Part 10) and filters
; by isAtomInAf inside, so the $atom values match &sti-series entries
; exactly (both come from getAtomsInTypeSpace / TypeSpace, not &af).
(= (cairn-collect-af-trends)
   (let $all-atoms (getAtomsInTypeSpace)
        (collapse
           (let $atom (superpose $all-atoms)
                (if (isAtomInAf $atom)
                    (let* (($trend (sti-trend $atom))
                           ($vol   (sti-volatility $atom)))
                       (TrendEntry $atom $trend $vol))
                    (empty))))))
