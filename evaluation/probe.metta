; =============================================================
; CAIRN – Probe Metrics  (spec §3.3)
;
; Cognitive maintenance (mean AF Jaccard over CIP series) and
; glocal coordination (√(local_coh × global_coh) on Hebbian communities).
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
;             tools/utils.py (identify_communities, via py-call)
; =============================================================

; ---- Private helpers ------------------------------------------

(= (pair-first (pair $a $b)) $a)
(= (pair-second (pair $a $b)) $b)

; Consecutive (overlapping) pairs from a cons-list: (a b c) -> ((pair a b) (pair b c))
(= (consecutive-pairs ()) ())
(= (consecutive-pairs (cons $_ ())) ())
(= (consecutive-pairs (cons $a (cons $b $rest)))
   (cons (pair $a $b) (consecutive-pairs (cons $b $rest))))

; Index of the community (0-based) containing $atom, or -1 if none.
; O(communities), early-exits on first match -- avoids the O(communities^2)
; blowup of a per-pair link re-scan.
(= (community-index-of $atom () $i) -1)
(= (community-index-of $atom (cons $c $cs) $i)
   (if (member-expr $atom $c)
       $i
       (community-index-of $atom $cs (+ $i 1))))

; A Hebbian link is inter-community iff its endpoints resolve to two
; different (both-found) community indices. One pass over the links,
; O(links x communities) total -- no per-pair link re-scan.
(= (classify-link $link $communities)
   (let* (($src (get-hlink-source $link))
          ($tgt (get-hlink-target $link))
          ($si  (community-index-of $src $communities 0))
          ($ti  (community-index-of $tgt $communities 0)))
      (if (== $si $ti)
          (empty)
          (if (< $si 0)
              (empty)
              (if (< $ti 0)
                  (empty)
                  $link)))))

(= (inter-community-links $links $communities)
   (collapse (let $link (superpose $links) (classify-link $link $communities))))

; (src tgt weight) — weight = Hebb STV mean, defaulted in Python if 0.
(= (links-to-edges $links)
   (collapse
      (let $link (superpose $links)
           (let* (($src (get-hlink-source $link))
                  ($tgt (get-hlink-target $link))
                  ($w   (get-hlink-probability $src $tgt)))
              ($src $tgt $w)))))

; Weighted Louvain (networkx) over all Hebbian links.
(= (identify-communities $links)
   (py-call (utils.identify_communities (links-to-edges $links))))

; ---- §3.3  Trajectory Test: Cognitive Maintenance -------------
; Average pairwise AF Jaccard similarity (measure-context-retention)
; across consecutive snapshots in a CIP series.

(= (measure-cognitive-maintenance $cip-series)
   (let* (($pairs    (consecutive-pairs $cip-series))
          ($overlaps (map-flat (|-> ($p) (measure-context-retention (pair-first $p) (pair-second $p))) $pairs)))
      (average $overlaps)))

; ---- §3.3  Coordination Test: Glocal Coordination --------------
; Geometric mean of local (within-community) and global (cross-community,
; link-probability vs. temporal-conjunction correlation) coherence
; over the Hebbian-link community structure. Degrades to 0.0 when
; there are 0 or 1 communities (average/pearson-correlation already
; return 0.0 for empty input -- no extra guard needed).

(= (measure-glocal-coordination)
   (let* (($all-links        (get-all-hlinks))
          ($communities      (identify-communities $all-links))
          ($local-coherence  (average (map-flat measure-coherence $communities)))
          ($inter-links      (inter-community-links $all-links $communities))
          ($link-probs       (map-flat (|-> ($l) (get-hlink-probability (get-hlink-source $l) (get-hlink-target $l))) $inter-links))
          ($conjunctions     (map-flat (|-> ($l) (temporal-conjunction (get-hlink-source $l) (get-hlink-target $l))) $inter-links))
          ($global-coherence (pearson-correlation $link-probs $conjunctions)))
      (sqrt-math (* $local-coherence $global-coherence))))
