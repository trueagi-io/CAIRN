; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_homology.metta
; Tests the pure MeTTa parts of tools/homology.metta.
; persistent-homology-invariants requires networkx via py-call and is
; left for integration testing.

; ---- Stub metta-attention API --------------------------------

!(bind! &typeSpace (new-space))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a b) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK b c) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a c) stub))

; ---- Load module under test ----------------------------------

!(import! &self "../tools/utils.py")
!(import! &self tools/homology)

; ---- Helpers -------------------------------------------------

(= (assert-eq $label $expected $actual)
   (if (== $expected $actual)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

; ---- TopologyReport field accessors --------------------------

!(let $report (TopologyReport 5 2 3 0)
   (let* (($_ (assert-eq topology-triangles 5 (topology-triangles $report)))
          ($_ (assert-eq topology-betti-0   2 (topology-betti-0   $report)))
          ($_ (assert-eq topology-betti-1   3 (topology-betti-1   $report)))
          ($_ (assert-eq topology-betti-2   0 (topology-betti-2   $report))))
         done))

; ---- hlinks-to-edge-list -------------------------------------

; Three stubbed links → three (src tgt) pairs
!(let $edges (hlinks-to-edge-list)
   (assert-eq hlinks-to-edge-list-count 3 (size-atom $edges)))

; ---- count_voids (Betti-2) ------------------------------------

; Simple graph (triangle): edges form a cycle with no 2D voids
; Expected: Betti-2 = 0 (no enclosed voids in a 1-skeleton)
!(let $edges (hlinks-to-edge-list)
   (let $betti_2 (py-call (utils.count_voids $edges))
      (assert-eq count-voids-simple-graph 0 $betti_2)))

; Full pipeline: the stubbed triangle is a filled 2-simplex once cliques
; are expanded, so persistent-homology-invariants must report Betti-1 = 0
; (contractible), not the raw 1-skeleton cycle-rank of 1.
!(let $report (persistent-homology-invariants)
   (assert-eq persistent-homology-betti-1-filled-triangle 0 (topology-betti-1 $report)))
