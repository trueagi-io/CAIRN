; =============================================================
; CAIRN – STI/LTI Time Series  (spec §4.1)
;
; Maintains a per-atom history of STI and LTI values, appended
; at each CIP boundary.
;
; Storage: two spaces, one entry per atom:
;   (sti-entry <atom> <list-newest-first>)
; Values are built with cons-atom (proper Prolog lists) so that
; reverse-acc's (cons $h $t) pattern can match them.
;
; Depends on: metta-attention API
;               getSti, getLti, getAtomsInTypeSpace
;             tools/utils (average, standard-deviation,
;               pointwise-product, pearson-correlation, member-expr,
;               get-all-hlinks, get-hlink-source/target/probability,
;               hlink-probs) -- caller must pre-import this; this
;               file must load AFTER tools/utils
;
; temporal-conjunction, measure-coherence, get-hlinks-within, and
; hlink-conjunctions/hlink-conjs-acc live here rather than in
; tools/utils.metta because temporal-conjunction needs get-sti-series
; (defined in this file) -- keeping them here avoids a circular
; import between tools/utils.metta and tools/timeseries.metta.
; =============================================================

!(bind! &sti-series (new-space))
!(bind! &lti-series (new-space))

; ---- Internal: safe lookup ----------------------------------

; Returns the stored cons-list for $atom, or () if not yet recorded.
(= (series-get $space $tag $atom)
   (let $hits (collapse (match $space ($tag $atom $vals) $vals))
        (if (== $hits ()) () (car-atom $hits))))

; ---- Record -------------------------------------------------

; Append current STI and LTI of every atom to their series.
; Call at each CIP boundary before the AtomSpace is updated.
(= (record-cip-series)
   (let $all-atoms (getAtomsInTypeSpace)
        (collapse
            (let $atom (superpose $all-atoms)
                 (let* (($curr-sti  (getSti $atom))
                        ($curr-lti  (getLti $atom))
                        ($prev-sti  (series-get &sti-series sti-entry $atom))
                        ($prev-lti  (series-get &lti-series lti-entry $atom))
                        ($new-sti   (cons-atom $curr-sti $prev-sti))
                        ($new-lti   (cons-atom $curr-lti $prev-lti))
                        ($_ (if (== $prev-sti ())
                                ()
                                (remove-atom &sti-series (sti-entry $atom $prev-sti))))
                        ($_ (if (== $prev-lti ())
                                ()
                                (remove-atom &lti-series (lti-entry $atom $prev-lti))))
                        ($_ (add-atom &sti-series (sti-entry $atom $new-sti)))
                        ($_ (add-atom &lti-series (lti-entry $atom $new-lti))))
                      done)))))

; ---- Read ---------------------------------------------------

; Returns the STI history of $atom in chronological order (oldest first).
(= (get-sti-series $atom)
   (reverse-list (series-get &sti-series sti-entry $atom)))

; Returns the LTI history of $atom in chronological order (oldest first).
(= (get-lti-series $atom)
   (reverse-list (series-get &lti-series lti-entry $atom)))

; ---- Windowed queries ----------------------------------------

; Return the most recent N STI values for $atom (newest first).
(= (last-n-sti $atom $n)
   (take-n $n (series-get &sti-series sti-entry $atom)))

; Return the most recent N LTI values for $atom (newest first).
(= (last-n-lti $atom $n)
   (take-n $n (series-get &lti-series lti-entry $atom)))

; Take the first N elements of a cons list.
(= (take-n $n ()) ())
(= (take-n $n (cons $h $t))
   (if (<= $n 0) ()
       (cons $h (take-n (- $n 1) $t))))

; ---- Analysis -----------------------------------------------

; Series of consecutive STI differences (newest delta first).
(= (sti-delta-series $atom)
   (delta-pairs (series-get &sti-series sti-entry $atom)))

(= (delta-pairs ()) ())
(= (delta-pairs (cons $_ ())) ())
(= (delta-pairs (cons $a (cons $b $rest)))
   (cons (- $a $b) (delta-pairs (cons $b $rest))))

; STI trend for $atom: rising, falling, or stable.
; Compares the most recent value to the series average.
(= (sti-trend $atom)
   (let $series (series-get &sti-series sti-entry $atom)
        (if (== $series ())
            stable
            (let* (($latest (car-atom $series))
                   ($chrono (reverse-list $series))
                   ($avg    (average $chrono))
                   ($diff   (- $latest $avg)))
                  (if (> $diff 0.0) rising
                      (if (< $diff 0.0) falling
                          stable))))))

; STI volatility (standard deviation of the series).
(= (sti-volatility $atom)
   (let $series (reverse-list (series-get &sti-series sti-entry $atom))
        (if (== $series ())
            0.0
            (standard-deviation $series))))

; ---- Helper -------------------------------------------------

(= (reverse-list $list) (reverse-acc $list ()))
(= (reverse-acc () $acc) $acc)
(= (reverse-acc (cons $h $t) $acc) (reverse-acc $t (cons $h $acc)))

; ---- Temporal conjunction: time-averaged STI co-activation --

(= (temporal-conjunction $atom-i $atom-j)
   (let* (($sti-i (get-sti-series $atom-i))
          ($sti-j (get-sti-series $atom-j)))
      (if (== $sti-i ())
          0.0
          (if (== $sti-j ())
              0.0
              (average (pointwise-product $sti-i $sti-j))))))

; ---- Coherence: Pearson correlation of link probs vs temporal conjunctions

(= (measure-coherence $atoms)
   (let $hlinks (get-hlinks-within $atoms)
        (if (== $hlinks ())
            0.0
            (let* (($probs  (hlink-probs $hlinks))
                   ($conjs  (hlink-conjunctions $hlinks)))
                (pearson-correlation $probs $conjs)))))

; Hebbian links where both endpoints are in $atoms.
; Uses member-expr (structural ==) -- suitable for MeTTa-side atom sets
; such as module partitions from identify-modules.
(= (get-hlinks-within $atoms)
   (collapse
      (let $link (superpose (get-all-hlinks))
           (let* (($src (get-hlink-source $link))
                  ($tgt (get-hlink-target $link)))
              (if (member-expr $src $atoms)
                  (if (member-expr $tgt $atoms)
                      $link
                      (empty))
                  (empty))))))

; All Hebbian links whose SOURCE is currently in the Attentional Focus,
; regardless of target. Queries &typeSpace once per AF atom with the source
; bound (get-hlinks-from) instead of scanning every Hebbian link ever
; created -- cost scales with AF size and each atom's own out-degree, not
; with the total link count accumulated over the whole run. get-hlinks-from's
; result is bound via let before superpose (bind-before-use -- superposing a
; function call inline instead of a bound variable silently failed to
; evaluate under PeTTa; verified empirically before landing this pattern).
(= (get-hlinks-from-af)
   (let $af (getAfAtoms)
        (collapse
           (let $src (superpose $af)
                (let $from-src (get-hlinks-from $src)
                     (superpose $from-src))))))

; All Hebbian links whose TARGET is currently in the Attentional Focus,
; regardless of source. Mirrors get-hlinks-from-af using get-hlinks-to.
(= (get-hlinks-to-af)
   (let $af (getAfAtoms)
        (collapse
           (let $tgt (superpose $af)
                (let $to-tgt (get-hlinks-to $tgt)
                     (superpose $to-tgt))))))

; Hebbian links where both endpoints are currently in the Attentional Focus:
; the subset of get-hlinks-from-af (source already in AF) whose target is
; also in AF. isAtomInAf returns lowercase true/false (PeTTa parser
; canonicalizes True→true).
(= (get-hlinks-in-af)
   (let $src-touching (get-hlinks-from-af)
        (collapse
           (let $link (superpose $src-touching)
                (let $tgt (get-hlink-target $link)
                     (if (isAtomInAf $tgt)
                         $link
                         (empty)))))))

; Cons-list of temporal conjunctions for a flat Expression of Hebbian links.
(= (hlink-conjunctions $links)
   (hlink-conjs-acc $links ()))
(= (hlink-conjs-acc $links $acc)
   (if (== $links ())
       $acc
       (let* (($link (car-atom $links))
              ($rest (cdr-atom $links))
              ($src  (get-hlink-source $link))
              ($tgt  (get-hlink-target $link))
              ($tc   (temporal-conjunction $src $tgt)))
          (hlink-conjs-acc $rest (cons-atom $tc $acc)))))
