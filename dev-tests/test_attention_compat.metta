; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_attention_compat.metta
;
; metta-attention after the Aug 2026 run:
;   test-superpose was renamed to agent-runner
;   the attention-bank truth-value constructor is (stv mean conf), not (STV ...)
; This loads the real bank (no knowledge graph) and checks both.

(= (match-count $space $pattern)
   (size-atom (collapse (match $space $pattern True))))

(= (find $space $pattern)
   (if (> (match-count $space $pattern) 0) True False))

(= (unify $a $b $then $else)
   (let $hits (collapse (match $a $b $then))
        (if (== $hits ())
            $else
            (superpose $hits))))

!(import! &self ../metta-attention/attention-bank/utilities/helper-functions)
!(import! &self ../metta-attention/attention-bank/utilities/recentVal)
!(import! &self ../metta-attention/attention/AttentionParam)
!(import! &self ../metta-attention/attention/baching)
!(import! &self ../metta-attention/attention-bank/attention-value/getter-and-setter)
!(import! &self ../metta-attention/attention-bank/bank/importance-index/importance-index)
!(import! &self ../metta-attention/attention/Neighbors)
; .py imports resolve from this file's directory, not the CAIRN cwd.
!(import! &self "../../metta-attention/experiments/utils/logger.py")
!(import! &self ../metta-attention/experiments/logger)
!(import! &self ../metta-attention/attention-bank/bank/attentional-focus/attentional-focus)
!(import! &self ../metta-attention/attention-bank/bank/attention-bank)
!(import! &self ../metta-attention/attention-bank/bank/stochastic-importance-diffusion/stochastic-importance-diffusion)
!(import! &self ../metta-attention/attention/RentCollectionAgent/RentCollectionBaseAgent/RentCollectionBaseAgent)
!(import! &self ../metta-attention/attention/RentCollectionAgent/WARentCollectionAgent/WARentCollectionAgent)
!(import! &self ../metta-attention/attention/RentCollectionAgent/AFRentCollectionAgent/AFRentCollectionAgent)
!(import! &self ../metta-attention/attention/ImportanceDiffusionAgent/ImportanceDiffusionBase/ImportanceDiffusionBase)
!(import! &self ../metta-attention/attention/ImportanceDiffusionAgent/WAImportanceDiffusionAgent/WAImportanceDiffusionAgent)
!(import! &self ../metta-attention/attention/ImportanceDiffusionAgent/AFImportanceDiffusionAgent/AFImportanceDiffusionAgent)
!(import! &self "../../metta-attention/attention/ImportanceDiffusionAgent/getelement.py")
!(import! &self ../metta-attention/attention/HebbianUpdatingAgent/HebbianUpdatingAgent)
!(import! &self ../metta-attention/attention/HebbianCreationAgent/HebbianCreationAgent)
!(import! &self ../metta-attention/attention/runner-Def)
!(import! &self tools/utils)

(= (assert-eq $label $expected $actual)
   (if (== $expected $actual)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

; Batched STI scan must read the lowercase constructor the bank now writes.
!(assert-eq sti-from-av-cell 3.0
   (typespace-value-sti ((AV 3.0 1.0 0.0) (Bin 1.0))))
!(assert-eq sti-from-stv-cell 7.0
   (typespace-value-sti (((stv 0.5 0.9) (AV 7.0 2.0 0.0)) (Bin 2.0))))
!(assert-eq uppercase-STV-is-not-a-cell 0.0
   (typespace-value-sti (((STV 0.5 0.9) (AV 7.0 2.0 0.0)) (Bin 2.0))))

; Live bank: setAv then setStv keeps both, and getSti/getMean still agree.
!(setAv liveAtom (4.0 1.0 0.0))
!(setStv liveAtom (0.2 0.9))
!(assert-eq live-getSti 4.0 (getSti liveAtom))
!(assert-eq live-getMean 0.2 (getMean liveAtom))
!(let $cell (getValueType liveAtom)
   (assert-eq live-typespace-sti 4.0 (typespace-value-sti $cell)))

!(setStv (ASYMMETRIC_HEBBIAN_LINK a b) (0.8 0.9))
!(assert-eq hebb-mean 0.8 (getMean (ASYMMETRIC_HEBBIAN_LINK a b)))

; The renamed entry point must actually run, not stay an unevaluated call.
!(bind! &incident (new-space))
!(once (let $r (collapse (agent-runner &incident))
        (if (== $r ((agent-runner &incident)))
            (println! (FAIL agent-runner-not-defined))
            (println! (PASS agent-runner-ran)))))
