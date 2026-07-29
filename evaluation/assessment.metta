; =============================================================
; CAIRN – Assessment Metrics  (spec §3.2)
;
; Coherence, context retention, distributed importance,
; selective modulation, connection ratio.
;
; Depends on: tools/utils (variance, minimum, maximum,
;             pearson-correlation, get-all-hlinks,
;             get-hlink-source, get-hlink-target, member-expr)
;             tools/timeseries (get-sti-series, measure-coherence)
;             -- caller must pre-import this, AFTER tools/utils
;             tools/cip (cip-af) -- caller must pre-import this
;             metta-attention API (getAfAtoms, getAtomsInTypeSpace,
;             getSti, getLti, isAtomInAf)
; =============================================================

; ---- §3.2.1  Attention Coherence ----------------------------
; Coherence of AF members: Pearson correlation between Hebbian
; link probabilities and temporal conjunctions within the AF.
; Uses get-hlinks-in-af (isAtomInAf-based) rather than
; get-hlinks-within(getAfAtoms) because getAfAtoms returns Python-
; side atom references that do not structurally match (==) the
; source/target atoms stored in &typeSpace Hebbian link keys.

(= (measure-attention-coherence)
   (let $hlinks (get-hlinks-in-af)
        (if (== $hlinks ())
            0.0
            (let* (($probs  (hlink-probs $hlinks))
                   ($conjs  (hlink-conjunctions $hlinks)))
                (pearson-correlation $probs $conjs)))))

; ---- §3.2.2  Context Retention ------------------------------
; Jaccard similarity of AF membership between two CIP snapshots.

(= (measure-context-retention $prev-cip $curr-cip)
   (let* (($prev-af  (cip-af $prev-cip))
          ($curr-af  (cip-af $curr-cip))
          ($overlap  (* 1.0 (size-atom (intersection-atom $prev-af $curr-af))))
          ($sz-a     (* 1.0 (size-atom $prev-af)))
          ($sz-b     (* 1.0 (size-atom $curr-af)))
          ($union-sz (- (+ $sz-a $sz-b) $overlap)))
      (if (> $union-sz 0.0)
          (/ $overlap $union-sz)
          0.0)))

; ---- §3.2.3  Distributed Importance ------------------------------
; Pearson(mean STI series, LTI) over typeSpace. Θ(N·T).

(= (measure-distributed-importance)
   (let $atoms (getAtomsInTypeSpace)
        (if (== $atoms ())
            0.0
            (let* (($mean-stis (collect-mean-stis $atoms))
                   ($ltis      (collect-ltis $atoms)))
                (pearson-correlation $mean-stis $ltis)))))

(= (collect-mean-stis $atoms)
   (if (== $atoms ())
       ()
       (let* (($atom (car-atom $atoms))
              ($rest (cdr-atom $atoms))
              ($series (get-sti-series $atom))
              ($mean (if (== $series ()) 0.0 (average $series))))
          (cons-atom $mean (collect-mean-stis $rest)))))

(= (collect-ltis $atoms)
   (if (== $atoms ())
       ()
       (let* (($atom (car-atom $atoms))
              ($rest (cdr-atom $atoms))
              ($lti  (let $r (collapse (getLti $atom))
                          (if (== $r ()) 0.0 (* 1.0 (car-atom $r))))))
          (cons-atom $lti (collect-ltis $rest)))))

; ---- §3.2.4  Selective Modulation ---------------------------
; Var(STI) / ((max-min)^2/12) — range-uniform null. Θ(N).

(= (measure-selective-modulation)
   (let $atoms (getAtomsInTypeSpace)
        (if (== $atoms ())
            0.0
            (let* (($stis (collect-stis $atoms))
                   ($var  (variance $stis))
                   ($lo   (minimum $stis))
                   ($hi   (maximum $stis))
                   ($span (- $hi $lo))
                   ($uvar (/ (* $span $span) 12.0)))
                (if (> $uvar 0.0) (/ $var $uvar) 0.0)))))

(= (collect-stis $atoms)
   (if (== $atoms ())
       ()
       (let* (($atom (car-atom $atoms))
              ($rest (cdr-atom $atoms))
              ($sti  (let $r (collapse (getSti $atom))
                          (if (== $r ()) 0.0 (* 1.0 (car-atom $r))))))
          (cons-atom $sti (collect-stis $rest)))))

; ---- §3.2.5  Connection Ratio --------------------------------
; internal AF-out / all AF-out Hebbian links.

(= (measure-connection-ratio)
   (let $from-af (get-hlinks-from-af)
        (if (== $from-af ())
            0.0
            (let* (($total (* 1.0 (size-atom $from-af)))
                   ($int   (* 1.0 (size-atom
                              (collapse
                                 (let $l (superpose $from-af)
                                      (if (isAtomInAf (get-hlink-target $l))
                                          $l
                                          (empty))))))))
                (/ $int $total)))))
