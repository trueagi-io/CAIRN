; =============================================================
; CAIRN – Evaluation Pipeline Demo
;
; Full reproduction of the metta-attention insect/poison
; experiment with CAIRN recording CIP snapshots and attention
; metrics at each agent-run boundary.
;
; Run from the CAIRN directory:
;   source venv/bin/activate
;   ../PeTTa/run.sh demo.metta
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

; ---- Result recording ----------------------------------------

!(cairn-init-recorder)
!(bind! &last-snap (new-state none))

; ---- Experiment loop (mirrors experiment.metta) --------------
; Progress prints mark each expensive step so a silent hang is
; attributable (series scan vs agents vs CIP record vs stimulate).
; stimulate is wrapped in collapse like experiment.metta -- bare
; stimulate can leave PeTTa exploring nondeterministic branches.

(= (batch) 25)

(= (run-experiment $expr $counter $cip-index $baseline-snap $prev-snap)
   (if (== $expr ())
       done
       (let* (($now  (car-atom $expr))
              ($rest (cdr-atom $expr))
              ($_ (println! (read-step $counter word $now remaining (size-atom $rest))))
              ($_ (collapse (stimulate $now 30)))
              ($_ (println! (stimulating: $now))))
           (if (or (== (% $counter (batch)) 0) (== $rest ()))
               (let* (($_ (println! (--- Running agents batch boundary ---)))
                      ($_ (collapse (test-superpose &incident)))
                      ($_ (println! (agents done - recording CIP series)))
                      ($_ (record-cip-series))
                      ($_ (println! (CIP series done - snapshot-now)))
                      ($snap (snapshot-now $cip-index))
                      ($_ (change-state! &last-snap $snap))
                      ($_ (println! (snapshot done - cairn-record-cip)))
                      ($_ (if (== $prev-snap none)
                              (cairn-record-cip-baseline $cip-index)
                              (cairn-record-cip $cip-index $baseline-snap $prev-snap $snap)))
                      ($_ (println! (CIP: $cip-index)))
                      ($_ (println! (AF: (getAfAtoms))))
                      ($_ (println! (AF-size-ratio: (measure-af-size-ratio)))))
                   (run-experiment $rest (+ $counter 1) (+ $cip-index 1) $baseline-snap $snap))
               (let* (($_ (println! (continued to stimulate batched atoms))))
                   (run-experiment $rest (+ $counter 1) $cip-index $baseline-snap $prev-snap))))))

; ==============================================================
; RUN
; ==============================================================

!(println! (=== CAIRN Evaluation Pipeline Demo ===))
!(println! (Reproducing metta-attention insect/poison experiment))
!(println! ())

; Baseline CIP -- each step is logged. If the run goes silent after
; a "starting" line, that step is the stall (not a mystery hang).
!(println! (baseline starting record-cip-series full-typeSpace STI-LTI scan))
!(record-cip-series)
!(println! (baseline record-cip-series done - snapshot-now 0))
!(bind! &baseline-snap (new-state (snapshot-now 0)))
!(println! (baseline snapshot-now done - cairn-record-cip-baseline 0))
!(cairn-record-cip-baseline 0)
!(println! (baseline CIP 0 recorded - starting stimulus loop))

; Process insect sentences (same as experiment.metta)
!(let $sentences (collapse (match &insect (insectSent $x) $x))
   (let* (($words (car-atom $sentences))
          ($_ (println! (stimulus words loaded: (size-atom $words)))))
      (run-experiment $words 1 1
                      (get-state &baseline-snap)
                      (get-state &baseline-snap))))

; ---- Final CAIRN Report --------------------------------------

!(println! ())
!(println! (=== Final CAIRN Report ===))

!(println! ())
!(println! (--- Resource Metrics ---))
!(let $r (measure-af-size-ratio)    (println! (AF-size-ratio: $r)))
!(let $c (measure-sti-concentration) (println! (STI-concentration: $c)))
!(let $d (measure-link-density)      (println! (Link-density: $d)))

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

!(cairn-close-recorder)
!(println! (Results written to output/metrics.csv and output/summary.json))

!(println! ())
!(println! (Done.))
