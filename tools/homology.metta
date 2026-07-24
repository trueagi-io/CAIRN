; =============================================================
; CAIRN – Topological Analysis  (spec §4.4)
;
; Computes Betti numbers and triangle count from the Hebbian
; link graph.  Graph algorithms delegate to tools/utils.py via
; py-call (networkx clique enumeration + mod-2 boundary-matrix
; rank -- deterministic, no external homology library).
;
; TopologyReport constructor:
;   (TopologyReport $triangles $betti-0 $betti-1 $betti-2)
;
; Depends on: metta-attention API (&typeSpace, ASYMMETRIC_HEBBIAN_LINK)
;             tools/utils.py (topology_invariants -- single-shot + cache)
; =============================================================

; ---- Record -------------------------------------------------

(: TopologyReport Type)

(= (topology-triangles (TopologyReport $t $_ $_ $_)) $t)
(= (topology-betti-0   (TopologyReport $_ $b $_ $_)) $b)
(= (topology-betti-1   (TopologyReport $_ $_ $c $_)) $c)
(= (topology-betti-2   (TopologyReport $_ $_ $_ $d)) $d)

; ---- Edge list ----------------------------------------------

; Collect all Hebbian links as a flat Expression of (src tgt) pairs.
(= (hlinks-to-edge-list)
   (collapse (match &typeSpace ((ASYMMETRIC_HEBBIAN_LINK $src $tgt) $_)
                               ($src $tgt))))

; ---- Invariants ---------------------------------------------

; Topological invariants of the Hebbian link graph (spec §4.4).
;   Betti-0 : connected components
;   Betti-1 : independent cycles
;   Betti-2 : higher-order voids (via mod-2 rank of the clique complex)
; Single py-call: one graph build, size-bounded cliques, fingerprint cache.
; Python returns a 4-list [tri, b0, b1, b2]; unpack with car/cdr so both
; Prolog lists and Expression-shaped returns work under PeTTa/Janus.
(= (persistent-homology-invariants)
   (let $edges (hlinks-to-edge-list)
        (let $vals (py-call (utils.topology_invariants $edges))
             (let* (($t  (car-atom $vals))
                    ($r1 (cdr-atom $vals))
                    ($b0 (car-atom $r1))
                    ($r2 (cdr-atom $r1))
                    ($b1 (car-atom $r2))
                    ($b2 (car-atom (cdr-atom $r2))))
                   (TopologyReport $t $b0 $b1 $b2)))))
