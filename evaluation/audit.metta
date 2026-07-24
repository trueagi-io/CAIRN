; =============================================================
; CAIRN – Audit Metrics  (spec §3.3, Phase II)
;
; Audits the global allocation of STI across the entire typeSpace
; (not just the Attentional Focus), independent of resource/
; effectiveness/assessment metrics.
;
; Depends on: tools/utils (sum, minimum, shannon-entropy, map-flat)
;             -- caller must pre-import this (e.g. via evaluation/resource,
;             which already self-imports it; see evaluation/assessment.metta
;             for the same convention re: tools/cip)
;             metta-attention API (getAtomsInTypeSpace, getSti)
; =============================================================

; ---- §3.3.1  Preallocation Space ----------------------------
; Normalized Shannon entropy of the STI distribution across all
; atoms in the typeSpace. Near 0 = STI tightly concentrated on a
; few atoms; near 1 = STI spread near-uniformly across all atoms.

(= (measure-preallocation-space)
   (let* (($atoms (getAtomsInTypeSpace))
          ($n      (size-atom $atoms)))
      (if (> $n 1)
          (let* (($stis    (collapse (let $a (superpose $atoms) (getSti $a))))
                 ($min-sti (minimum $stis))
                 ($shifted (map-flat (|-> ($s) (- $s $min-sti)) $stis))
                 ($total   (sum $shifted))
                 ($dist    (if (> $total 0.0)
                               (map-flat (|-> ($s) (/ $s $total)) $shifted)
                               $shifted))
                 ($entropy (shannon-entropy $dist)))
              (/ $entropy (log-math 2 (* 1.0 $n))))
          0.0)))
