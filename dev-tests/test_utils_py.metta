; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_utils_py.metta
; Tests the Python functions in tools/utils.py via py-call.

; ---- Load Python module --------------------------------------

!(import! &self "../tools/utils.py")

; ---- Helpers -------------------------------------------------

(= (assert-eq $label $expected $actual)
   (if (== $expected $actual)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

(= (assert-approx $label $expected $actual $tol)
   (let* (($diff (- $expected $actual))
          ($abs  (if (< $diff 0.0) (- 0.0 $diff) $diff))
          ($ok   (< $abs $tol)))
        (if $ok
            (println! (PASS $label))
            (println! (FAIL $label expected: $expected got: $actual)))))

; ---- Pearson Correlation -------------------------------------

!(let $corr (py-call (utils.pearson_correlation (0 1 2 3 4) (0 1 2 3 4)))
   (assert-approx pearson-perfect 1.0 $corr 0.001))

; ---- Shannon Entropy -----------------------------------------

!(let $h (py-call (utils.shannon_entropy (0.25 0.25 0.25 0.25)))
   (assert-approx shannon-uniform-4 2.0 $h 0.001))

; ---- Graph Topology ------------------------------------------

!(let $tri (py-call (utils.count_triangles ((a b) (b c) (a c))))
   (assert-eq triangles 1 $tri))

!(let $comp (py-call (utils.connected_components ((a b) (b c) (c d))))
   (assert-eq connected-components 1 $comp))

!(let $b2 (py-call (utils.count_voids ((a b) (b c) (c d) (d a))))
   (assert-eq betti-2-simple 0 $b2))

; A filled triangle is contractible (the 2-simplex fills the cycle) --
; betti-1 must be 0, not the raw graph cycle-rank of 1.
!(let $b1 (py-call (utils.count_undirected_cycles ((a b) (b c) (a c))))
   (assert-eq betti-1-filled-triangle 0 $b1))

; Octahedron graph (6 vertices, each non-adjacent only to its antipodal
; vertex: a-d, b-e, c-f) -- a triangulated 2-sphere with 8 faces enclosing
; exactly one genuine void.
!(let $edges
    ((a b) (a c) (a e) (a f) (b c) (b d) (b f) (c d) (c e) (d e) (d f) (e f))
   (let* (($tri (py-call (utils.count_triangles $edges)))
          ($b0  (py-call (utils.connected_components $edges)))
          ($b1  (py-call (utils.count_undirected_cycles $edges)))
          ($b2  (py-call (utils.count_voids $edges))))
      (let* (($_ (assert-eq octahedron-triangles 8 $tri))
             ($_ (assert-eq octahedron-betti-0    1 $b0))
             ($_ (assert-eq octahedron-betti-1    0 $b1))
             ($_ (assert-eq octahedron-betti-2    1 $b2)))
            done)))

; ---- Community Detection (Louvain) ----------------------------
; Round-trip shape check only (module membership / atom identity is
; covered more thoroughly in dev-tests/test_probe.metta). Asserting
; on module COUNT, not on exact element order within/between modules:
; Python set iteration order is not guaranteed stable across process
; runs (string hash randomization), even with a fixed Louvain seed.

!(let $modules (py-call (utils.identify_modules ((a b) (b c) (a c) (x y) (y z) (x z))))
   (assert-eq identify-modules-two-triangles 2 (size-atom $modules)))

!(let $modules (py-call (utils.identify_modules
                          ((a b 0.9) (b c 0.8) (a c 0.7) (x y 0.9) (y z 0.8) (x z 0.7))))
   (assert-eq identify-modules-weighted-two-triangles 2 (size-atom $modules)))
