; =============================================================
; CAIRN – Utilities (cons lists + stats). No timeseries import
; (timeseries depends on this file).
; =============================================================

!(import! &self (library lib_roman))   ; provides fold-flat, map-flat

; ---- Cons-List Utilities ------------------------------------

; Number of elements in a cons list.
(= (count ()) 0)
(= (count (cons $x $xs)) (+ 1 (count $xs)))

; Sum of a cons list of numbers.
(= (sum ()) 0.0)
(= (sum (cons $x $xs)) (+ $x (sum $xs)))

; Arithmetic mean of a cons list. Returns 0.0 for empty lists.
(= (average ()) 0.0)
(= (average $list)
   (let $n (count $list)
        (if (> $n 0) (/ (sum $list) $n) 0.0)))

; Minimum value in a non-empty cons list.
(= (minimum (cons $x ())) $x)
(= (minimum (cons $x $xs))
   (let $rest-min (minimum $xs)
        (if (< $x $rest-min) $x $rest-min)))

; ---- Statistical Functions ----------------------------------

(= (shannon-entropy ()) 0.0)
(= (shannon-entropy (cons $p $ps))
   (+ (if (> $p 0.0)
          (* (- 0.0 $p) (log-math 2 $p))
          0.0)
      (shannon-entropy $ps)))

(= (maximum (cons $x ())) $x)
(= (maximum (cons $x $xs))
   (let $rest-max (maximum $xs)
        (if (> $x $rest-max) $x $rest-max)))

; Standard deviation of a cons list. Returns 0.0 for empty lists.
; Uses manual recursion instead of fold-flat to avoid
; non-deterministic clause matching in lib_roman.
(= (standard-deviation $xs)
   (let $n (count $xs)
        (if (> $n 0)
            (let* (($mu  (/ (sum $xs) $n))
                   ($ssq (sum-sq-diff $xs $mu)))
                (sqrt-math (/ $ssq $n)))
            0.0)))

(= (sum-sq-diff () $_) 0.0)
(= (sum-sq-diff (cons $x $rest) $mu)
   (+ (* (- $x $mu) (- $x $mu))
      (sum-sq-diff $rest $mu)))


; ---- HebbianLink Accessors (metta-attention API) ------------

; Source and target atoms of an ASYMMETRIC_HEBBIAN_LINK expression.
(= (get-hlink-source (ASYMMETRIC_HEBBIAN_LINK $src $_)) $src)
(= (get-hlink-target (ASYMMETRIC_HEBBIAN_LINK $_ $tgt)) $tgt)

; STV mean of the HebbianLink between $src and $tgt. Returns 0.0 if the
; link has no STV (getMean fails or is not defined for this pair).
(= (get-hlink-probability $src $tgt)
   (let $result (collapse (getMean (ASYMMETRIC_HEBBIAN_LINK $src $tgt)))
        (if (== $result ()) 0.0 (car-atom $result))))

; All ASYMMETRIC_HEBBIAN_LINKs in the typeSpace as a flat Expression.
(= (get-all-hlinks)
   (collapse (match &typeSpace ((ASYMMETRIC_HEBBIAN_LINK $src $tgt) $_)
                               (ASYMMETRIC_HEBBIAN_LINK $src $tgt))))

; ASYMMETRIC_HEBBIAN_LINKs whose source is exactly $src. Binding $src before
; the match (rather than filtering &typeSpace afterward) restricts the scan
; to that one atom instead of enumerating every Hebbian link ever created --
; see get-hlinks-in-af in tools/timeseries.metta, which uses this to stay
; AF-scoped instead of re-scanning the whole (unboundedly growing) link
; history on every CIP.
(= (get-hlinks-from $src)
   (collapse (match &typeSpace ((ASYMMETRIC_HEBBIAN_LINK $src $tgt) $_)
                               (ASYMMETRIC_HEBBIAN_LINK $src $tgt))))

; ASYMMETRIC_HEBBIAN_LINKs whose target is exactly $tgt. Mirrors get-hlinks-from
; but binds the target position instead, for callers that need incoming links
; to a specific atom without a full &typeSpace scan (see get-hlinks-to-af).
(= (get-hlinks-to $tgt)
   (collapse (match &typeSpace ((ASYMMETRIC_HEBBIAN_LINK $src $tgt) $_)
                               (ASYMMETRIC_HEBBIAN_LINK $src $tgt))))

; ---- Whole-typeSpace STI extraction (batched, no per-atom lookup) ----

; Extracts an STI value from a &typeSpace value-cell, mirroring the shape
; matching metta-attention's own getAv/getSti do internally (see
; metta-attention/attention-bank/attention-value/getter-and-setter.metta) --
; not a change to that logic, just the same two known cell shapes read here
; so we can pull STI while scanning &typeSpace once, instead of matching it
; again individually per atom.
(= (typespace-value-sti $value)
   (case $value
     ( ( ((AV $sti $lti $vlti) (Bin $bin)) $sti)
       ( (((STV $a $b) (AV $sti $lti $vlti)) (Bin $bin)) $sti)
       ($else 0.0) )))

; All STI values in &typeSpace via a single combined scan: getAtomsInTypeSpace
; followed by one getSti call per atom re-searches &typeSpace once per atom
; (each a keyed lookup against the specific atom pattern); this instead reads
; the value already sitting next to each atom in the same pass. Order is not
; meaningful and not preserved -- callers only use this for population-level
; aggregates (sum, variance, entropy), which don't care about atom identity.
(= (all-typespace-stis)
   (collapse (match &typeSpace ($atom $value) (typespace-value-sti $value))))

; ---- Pearson correlation coefficient between two equal-length cons lists.
; Returns 0 when either list has zero variance.
; Uses manual recursion instead of fold-flat to avoid non-determinism.
(= (pearson-correlation $xs $ys)
   (let $n (count $xs)
        (if (> $n 0)
            (let* (($mx   (/ (sum $xs) $n))
                   ($my   (/ (sum $ys) $n))
                   ($num  (sum-cross-dev $xs $ys $mx $my))
                   ($varx (sum-sq-diff $xs $mx))
                   ($vary (sum-sq-diff $ys $my))
                   ($denom (sqrt-math (* $varx $vary))))
                (if (> $denom 0.0) (/ $num $denom) 0.0))
            0.0)))

; Sum of (xi - mx) * (yi - my) over paired cons lists.
(= (sum-cross-dev () () $_ $_) 0.0)
(= (sum-cross-dev (cons $x $xs) (cons $y $ys) $mx $my)
   (+ (* (- $x $mx) (- $y $my))
      (sum-cross-dev $xs $ys $mx $my)))

; ---- Variance of a cons list (population variance) ----------

(= (variance $xs)
   (let $n (count $xs)
        (if (> $n 0)
            (let* (($mu  (/ (sum $xs) $n))
                   ($ssq (sum-sq-diff $xs $mu)))
                (/ $ssq $n))
            0.0)))

; ---- Pointwise product of two cons lists, truncated to the ----
; shorter length (rather than failing) when lengths differ.

(= (pointwise-product () $_) ())
(= (pointwise-product (cons $a $as) ()) ())
(= (pointwise-product (cons $a $as) (cons $b $bs))
   (cons (* $a $b) (pointwise-product $as $bs)))

; ---- Expression membership (not cons-list — works on flat PeTTa expressions).
(= (member-expr $x $expr)
   (> (size-atom (collapse (let $e (superpose $expr)
                                (if (== $e $x) True (empty))))) 0))

; Cons-list of probabilities for a flat Expression of Hebbian links.
(= (hlink-probs ()) ())
(= (hlink-probs $links)
   (hlink-probs-acc $links ()))
(= (hlink-probs-acc $links $acc)
   (if (== $links ())
       $acc
       (let* (($link (car-atom $links))
              ($rest (cdr-atom $links))
              ($src  (get-hlink-source $link))
              ($tgt  (get-hlink-target $link))
              ($p    (get-hlink-probability $src $tgt)))
          (hlink-probs-acc $rest (cons-atom $p $acc)))))
