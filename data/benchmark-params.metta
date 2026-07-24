; =============================================================
; CAIRN – Benchmark optimized ECAN hyperparameters
;
; Values extracted from data/default-param-values.scm
; (OpenCog Scheme format — not directly PeTTa-parseable).
; Only the 5 params that differ from the mve.metta baseline
; are listed here; all others keep their mve.metta defaults.
;
; Baseline (mve.metta)  →  Optimized (this file)
;   MAX_AF_SIZE  70.0   →  500.0
;   TARGET_STI   1000.0 →  10000.0
;   TARGET_LTI   1000.0 →  10000.0
;   STI_FUNDS_BUFFER 1000.0 → 10000.0
;   LTI_FUNDS_BUFFER 1000.0 → 10000.0
; =============================================================

!(updateAttentionParam MAX_AF_SIZE      500.0)
!(updateAttentionParam TARGET_STI       10000.0)
!(updateAttentionParam TARGET_LTI       10000.0)
!(updateAttentionParam STI_FUNDS_BUFFER 10000.0)
!(updateAttentionParam LTI_FUNDS_BUFFER 10000.0)
