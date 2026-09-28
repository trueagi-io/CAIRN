; =============================================================
; CAIRN – Audit Metrics  (spec §3.3)
;
; Pre-allocation space: H(p̂) / log₂ n on min-shifted STI
; over typeSpace.
;
; Depends on: tools/utils (sum, minimum, shannon-entropy, map-flat)
;             -- caller must pre-import this (e.g. via evaluation/resource,
;             which already self-imports it; see evaluation/assessment.metta
;             for the same convention re: tools/cip)
;             metta-attention API (getAtomsInTypeSpace, getSti)
; =============================================================

; ---- §3.3.1  Preallocation Space ----------------------------
; H(min-shifted normalized STI) / log2(|atoms|).
; Named recursions instead of |-> : two lambdas in one clause trip a
; PeTTa numbervars error once earlier map-flat specializations exist.

(= (shift-sti $min ()) ())
(= (shift-sti $min (cons $s $rest))
   (cons (- $s $min) (shift-sti $min $rest)))

(= (scale-sti $total ()) ())
(= (scale-sti $total (cons $s $rest))
   (cons (/ $s $total) (scale-sti $total $rest)))

(= (measure-preallocation-space)
   (let* (($atoms (getAtomsInTypeSpace))
          ($n      (size-atom $atoms)))
      (if (> $n 1)
          (let* (($stis    (collapse (let $a (superpose $atoms) (getSti $a))))
                 ($min-sti (minimum $stis))
                 ($shifted (shift-sti $min-sti $stis))
                 ($total   (sum $shifted))
                 ($dist    (if (> $total 0.0)
                               (scale-sti $total $shifted)
                               $shifted))
                 ($entropy (shannon-entropy $dist)))
              (/ $entropy (log-math 2 (* 1.0 $n))))
          0.0)))
