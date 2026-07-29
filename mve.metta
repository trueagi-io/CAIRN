; =============================================================
; CAIRN – MVE
;
; Insect/poison run with full metric set: resource, local/global
; effectiveness, assessment (coherence, retention, distributed
; importance, selective modulation, connection ratio), audit,
; probe, topology.
;
; Run from the CAIRN directory:
;   source venv/bin/activate
;   ../PeTTa/run.sh mve.metta
; =============================================================

; ---- Polyfills for hyperon builtins not in PeTTa -------------

(= (match-count $space $pattern)
   (size-atom (collapse (match $space $pattern True))))

(= (find $space $pattern)
   (if (> (match-count $space $pattern) 0) True False))

(= (unify $a $b $then $else)
   (let $hits (collapse (match $a $b $then))
        (if (== $hits ())
            $else
            (superpose $hits))))

; ---- Import metta-attention core API -------------------------

!(import! &self ../metta-attention/attention-bank/utilities/helper-functions)
!(import! &self ../metta-attention/attention-bank/utilities/recentVal)
!(import! &self ../metta-attention/attention/AttentionParam)
!(import! &self ../metta-attention/attention/baching)
!(import! &self ../metta-attention/attention-bank/attention-value/getter-and-setter)
!(import! &self ../metta-attention/attention-bank/bank/importance-index/importance-index)
!(import! &self ../metta-attention/attention/Neighbors)

!(import! &self "../metta-attention/experiments/utils/logger.py")
!(import! &self ../metta-attention/experiments/logger)

!(import! &self ../metta-attention/attention-bank/bank/attentional-focus/attentional-focus)
!(import! &self ../metta-attention/attention-bank/bank/attention-bank)
!(import! &self ../metta-attention/attention-bank/bank/stochastic-importance-diffusion/stochastic-importance-diffusion)

; ---- Import ECAN agents --------------------------------------

!(import! &self ../metta-attention/attention/RentCollectionAgent/RentCollectionBaseAgent/RentCollectionBaseAgent)
!(import! &self ../metta-attention/attention/RentCollectionAgent/WARentCollectionAgent/WARentCollectionAgent)
!(import! &self ../metta-attention/attention/RentCollectionAgent/AFRentCollectionAgent/AFRentCollectionAgent)
!(import! &self ../metta-attention/attention/ImportanceDiffusionAgent/ImportanceDiffusionBase/ImportanceDiffusionBase)
!(import! &self ../metta-attention/attention/ImportanceDiffusionAgent/WAImportanceDiffusionAgent/WAImportanceDiffusionAgent)
!(import! &self ../metta-attention/attention/ImportanceDiffusionAgent/AFImportanceDiffusionAgent/AFImportanceDiffusionAgent)
!(import! &self "../metta-attention/attention/ImportanceDiffusionAgent/getelement.py")
!(import! &self ../metta-attention/attention/HebbianUpdatingAgent/HebbianUpdatingAgent)
!(import! &self ../metta-attention/attention/HebbianCreationAgent/HebbianCreationAgent)
!(import! &self ../metta-attention/attention/runner-Def)

; ---- Import CAIRN modules ------------------------------------

!(import! &self "tools/utils.py")
!(import! &self evaluation/resource)
!(import! &self evaluation/effectiveness)
!(import! &self tools/timeseries)
!(import! &self tools/homology)
!(import! &self evaluation/assessment)
!(import! &self evaluation/audit)
!(import! &self evaluation/probe)
!(import! &self "tools/recorder.py")
!(import! &self tools/recorder)

; ---- Load experiment data ------------------------------------

!(bind! &insect (new-space))
!(import! &insect ../metta-attention/experiments/data/insect-sent)

; static-import! loads the knowledge graph via pre-compiled .qlf
; (same mechanism as the original experiment.metta)
!(import! &self (library lib_import))
!(static-import! &incident ../metta-attention/experiments/data/kg)
!(println! (Knowledge graph loaded.))

; ---- ECAN hyperparameters (same as experiment.metta) ---------

!(updateAttentionParam MAX_AF_SIZE 70.0)
!(updateAttentionParam TARGET_STI 1000.0)
!(updateAttentionParam TARGET_LTI 1000.0)
!(updateAttentionParam STI_FUNDS_BUFFER 1000.0)
!(updateAttentionParam LTI_FUNDS_BUFFER 1000.0)
!(updateAttentionParam FUNDS_STI 100000.0)
!(updateAttentionParam FUNDS_LTI 100000.0)
!(updateAttentionParam TOPK 0.5)

; ---- Result recording (separate output dir from demo.metta) --

!(py-call (recorder.init_recorder "output/mve"))
!(bind! &last-snap (new-state none))

; ---- Full CIP recording: basic metrics + the 5 assessment ----
; metrics from evaluation/assessment.metta. Kept here (not in
; tools/recorder.metta) so demo.metta's recording path stays
; assessment-free.

(= (cairn-record-cip-full $cip-index $baseline-snap $prev-snap $snap)
   (let* (($af      (getAfAtoms))
          ($af-size (size-atom $af))
          ($ratio   (measure-af-size-ratio))
          ($conc    (measure-sti-concentration))
          ($density (measure-link-density))
          ($eff-g   (measure-global-effectiveness $baseline-snap $snap))
          ($eff-l   (measure-local-effectiveness $prev-snap $snap))
          ($delta   (aggregate-metric-delta $prev-snap $snap))
          ($cost    (total-resource-cost))
          ($topo    (persistent-homology-invariants))
          ($tri     (topology-triangles $topo))
          ($b0      (topology-betti-0 $topo))
          ($b1      (topology-betti-1 $topo))
          ($b2      (topology-betti-2 $topo))
          ($coh     (measure-attention-coherence))
          ($ret     (measure-context-retention $prev-snap $snap))
          ($di      (measure-distributed-importance))
          ($sel     (measure-selective-modulation))
          ($conn    (measure-connection-ratio))
          ($prealloc (measure-preallocation-space)))
      (py-call (recorder.record_cip
                  $cip-index $af-size
                  $ratio $conc $density
                  $eff-g $eff-l $delta $cost
                  $coh $ret $di $sel $conn $prealloc
                  $tri $b0 $b1 $b2))))

(= (cairn-record-cip-baseline-full $cip-index)
   (let* (($af      (getAfAtoms))
          ($af-size (size-atom $af))
          ($ratio   (measure-af-size-ratio))
          ($conc    (measure-sti-concentration))
          ($density (measure-link-density))
          ($coh     (measure-attention-coherence))
          ($di      (measure-distributed-importance))
          ($sel     (measure-selective-modulation))
          ($conn    (measure-connection-ratio))
          ($prealloc (measure-preallocation-space))
          ($topo    (persistent-homology-invariants))
          ($tri     (topology-triangles $topo))
          ($b0      (topology-betti-0 $topo))
          ($b1      (topology-betti-1 $topo))
          ($b2      (topology-betti-2 $topo)))
      (py-call (recorder.record_cip
                  $cip-index $af-size
                  $ratio $conc $density
                  "N/A" "N/A" "N/A" "N/A"
                  $coh "N/A" $di $sel $conn $prealloc
                  $tri $b0 $b1 $b2))))

; ---- Experiment loop (mirrors demo.metta, full recording) ----

(= (batch) 25)

(= (run-experiment-full $expr $counter $cip-index $baseline-snap $prev-snap)
   (if (== $expr ())
       done
       (let* (($now  (car-atom $expr))
              ($rest (cdr-atom $expr))
              ($_ (stimulate $now 30))
              ($_ (println! (stimulating: $now))))
           (if (or (== (% $counter (batch)) 0) (== $rest ()))
               (let* (($_ (println! (--- Running agents (batch boundary) ---)))
                      ($_ (collapse (test-superpose &incident)))
                      ($_ (record-cip-series))
                      ($snap (snapshot-now $cip-index))
                      ($_ (change-state! &last-snap $snap))
                      ($_ (change-state! &snap-history (cons-atom $snap (get-state &snap-history))))
                      ($_ (if (== $prev-snap none)
                              (cairn-record-cip-baseline-full $cip-index)
                              (cairn-record-cip-full $cip-index $baseline-snap $prev-snap $snap)))
                      ($_ (println! (CIP: $cip-index)))
                      ($_ (println! (AF: (getAfAtoms))))
                      ($_ (println! (AF-size-ratio: (measure-af-size-ratio)))))
                   (run-experiment-full $rest (+ $counter 1) (+ $cip-index 1) $baseline-snap $snap))
               (run-experiment-full $rest (+ $counter 1) $cip-index $baseline-snap $prev-snap)))))

; ==============================================================
; RUN
; ==============================================================

!(println! (=== CAIRN MVE: Full Evaluation Run ===))
!(println! (Insect/poison experiment with assessment metrics enabled))
!(println! ())

; Baseline CIP
!(record-cip-series)
!(bind! &baseline-snap (new-state (snapshot-now 0)))
!(bind! &snap-history (new-state (cons-atom (get-state &baseline-snap) ())))
!(cairn-record-cip-baseline-full 0)

; Process insect sentences (same as demo.metta)
!(let $sentences (collapse (match &insect (insectSent $x) $x))
   (run-experiment-full (car-atom $sentences) 1 1
                        (get-state &baseline-snap)
                        (get-state &baseline-snap)))

; ---- Final CAIRN Report --------------------------------------

!(println! ())
!(println! (=== Final CAIRN Report ===))

!(println! ())
!(println! (--- Resource Metrics ---))
!(let $r (measure-af-size-ratio)    (println! (AF-size-ratio: $r)))
!(let $c (measure-sti-concentration) (println! (STI-concentration: $c)))
!(let $d (measure-link-density)      (println! (Link-density: $d)))

!(println! ())
!(println! (--- Assessment Metrics ---))
!(let $coh (measure-attention-coherence)    (println! (Attention-coherence: $coh)))
!(let $di (measure-distributed-importance)       (println! (Distributed-importance: $di)))
!(let $sel (measure-selective-modulation)   (println! (Selective-modulation: $sel)))
!(let $conn (measure-connection-ratio)      (println! (Connection-ratio: $conn)))
!(let $prealloc (measure-preallocation-space) (println! (Preallocation-space: $prealloc)))

!(println! ())
!(println! (--- Topology ---))
!(let $hlinks (get-all-hlinks)
   (println! (Hebbian-links: (size-atom $hlinks))))
!(let $report (persistent-homology-invariants)
   (let* (($_ (println! (Triangles: (topology-triangles $report))))
          ($_ (println! (Connected-components: (topology-betti-0 $report))))
          ($_ (println! (Independent-cycles: (topology-betti-1 $report))))
          ($_ (println! (Voids: (topology-betti-2 $report)))))
         done))

!(println! ())
!(println! (--- Test Probing ---))
!(let $maint (measure-cognitive-maintenance (get-state &snap-history))
    (println! (Cognitive-maintenance: $maint)))
!(let $glocal (measure-glocal-coordination)
    (println! (Glocal-coordination: $glocal)))
; ---- Write summary and close recorder ------------------------

!(let $params ((MAX_AF_SIZE (getAttentionParam MAX_AF_SIZE))
               (TARGET_STI (getAttentionParam TARGET_STI))
               (TARGET_LTI (getAttentionParam TARGET_LTI))
               (FUNDS_STI (getAttentionParam FUNDS_STI))
               (FUNDS_LTI (getAttentionParam FUNDS_LTI))
               (TOPK (getAttentionParam TOPK))
               (batch_size (batch)))
    (cairn-write-summary $params
                         (get-state &baseline-snap)
                         (get-state &last-snap)))

!(let $maint  (measure-cognitive-maintenance (get-state &snap-history))
    (let $glocal (measure-glocal-coordination)
        (cairn-append-probe $maint $glocal)))

!(py-call (recorder.close_recorder))
!(println! (Results written to output/mve/metrics.csv and output/mve/summary.json))

!(println! ())
!(println! (Done.))
