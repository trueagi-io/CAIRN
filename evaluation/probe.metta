; =============================================================
; CAIRN – Test Probing  (spec §3.3, Phase III)
;
; Trajectory and coordination tests over the running CIP series
; and the Hebbian-link module structure.
;
; Depends on: tools/utils (average, pearson-correlation,
;             get-all-hlinks, get-hlink-source/target/probability,
;             member-expr, sqrt-math) -- caller must pre-import this
;             (e.g. via evaluation/resource, which already self-
;             imports it; see evaluation/assessment.metta for the
;             same convention re: tools/cip)
;             tools/timeseries (temporal-conjunction, measure-coherence)
;             -- caller must pre-import this, AFTER tools/utils
;             evaluation/assessment (measure-context-retention)
;             -- caller must pre-import this
;             tools/utils.py (identify_modules, via py-call)
; =============================================================

; ---- Private helpers ------------------------------------------

(= (pair-first (pair $a $b)) $a)
(= (pair-second (pair $a $b)) $b)

; Consecutive (overlapping) pairs from a cons-list: (a b c) -> ((pair a b) (pair b c))
(= (consecutive-pairs ()) ())
(= (consecutive-pairs (cons $_ ())) ())
(= (consecutive-pairs (cons $a (cons $b $rest)))
   (cons (pair $a $b) (consecutive-pairs (cons $b $rest))))

; Index of the module (0-based) containing $atom, or -1 if none.
; O(modules), early-exits on first match -- avoids the O(modules^2)
; blowup of the spec's literal module-pairs/get-hlinks-between design.
(= (module-index-of $atom () $i) -1)
(= (module-index-of $atom (cons $m $ms) $i)
   (if (member-expr $atom $m)
       $i
       (module-index-of $atom $ms (+ $i 1))))

; A Hebbian link is inter-module iff its endpoints resolve to two
; different (both-found) module indices. One pass over the links,
; O(links x modules) total -- no per-pair link re-scan.
(= (classify-link $link $modules)
   (let* (($src (get-hlink-source $link))
          ($tgt (get-hlink-target $link))
          ($si  (module-index-of $src $modules 0))
          ($ti  (module-index-of $tgt $modules 0)))
      (if (== $si $ti)
          (empty)
          (if (< $si 0)
              (empty)
              (if (< $ti 0)
                  (empty)
                  $link)))))

(= (inter-module-links $links $modules)
   (collapse (let $link (superpose $links) (classify-link $link $modules))))

; (src tgt weight) — weight = Hebb STV mean, defaulted in Python if 0.
(= (links-to-edges $links)
   (collapse
      (let $link (superpose $links)
           (let* (($src (get-hlink-source $link))
                  ($tgt (get-hlink-target $link))
                  ($w   (get-hlink-probability $src $tgt)))
              ($src $tgt $w)))))

; Weighted Louvain (networkx); all Hebbian links, same scope as SYNAPSE.
(= (identify-modules $links)
   (py-call (utils.identify_modules (links-to-edges $links))))

; ---- §3.3  Trajectory Test: Cognitive Maintenance -------------
; Average pairwise AF Jaccard similarity (measure-context-retention)
; across consecutive snapshots in a CIP series.

(= (measure-cognitive-maintenance $cip-series)
   (let* (($pairs    (consecutive-pairs $cip-series))
          ($overlaps (map-flat (|-> ($p) (measure-context-retention (pair-first $p) (pair-second $p))) $pairs)))
      (average $overlaps)))

; ---- §3.3  Coordination Test: Glocal Coordination --------------
; Geometric mean of local (within-module) and global (cross-module,
; link-probability vs. temporal-conjunction correlation) coherence
; over the Hebbian-link community structure. Degrades to 0.0 when
; there are 0 or 1 modules (average/pearson-correlation already
; return 0.0 for empty input -- no extra guard needed).

(= (measure-glocal-coordination)
   (let* (($all-links        (get-all-hlinks))
          ($modules          (identify-modules $all-links))
          ($local-coherence  (average (map-flat measure-coherence $modules)))
          ($inter-links      (inter-module-links $all-links $modules))
          ($link-probs       (map-flat (|-> ($l) (get-hlink-probability (get-hlink-source $l) (get-hlink-target $l))) $inter-links))
          ($conjunctions     (map-flat (|-> ($l) (temporal-conjunction (get-hlink-source $l) (get-hlink-target $l))) $inter-links))
          ($global-coherence (pearson-correlation $link-probs $conjunctions)))
      (sqrt-math (* $local-coherence $global-coherence))))
