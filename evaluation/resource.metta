; =============================================================
; CAIRN – Resource Metrics  (spec §2.1)
;
; AF size ratio, STI concentration, AF-internal link density.
; Each normalised to [0, 1].
;
; Depends on: metta-attention API (getAfAtoms, getAllAtomsWithBins,
;             getAtomsInTypeSpace, getSti, isAtomInAf, size-atom)
;             tools/utils (get-hlinks-from, get-hlink-target)
; =============================================================

!(import! &self tools/utils)
; NOTE: resource.metta is the designated sole self-importer of tools/utils
; in the mve.metta/demo.metta load chain. Downstream modules must NOT
; self-import it — doing so duplicates Prolog clauses (PeTTa has no import
; dedup), causing silent non-determinism. See dev-tests/test_regression.metta.

; ---- §2.1.1  AF Size Ratio -----------------------------------
; |AF| / |Atoms|.

(= (measure-af-size-ratio)
   (let* (($af    (getAfAtoms))
          ($af-n  (* 1.0 (size-atom $af)))
          ($all-n (* 1.0 (size-atom (getAllAtomsWithBins)))))
        (if (> $all-n 0.0) (/ $af-n $all-n) 0.0)))

; ---- §2.1.2  STI Concentration ------------------------------
; sum STI(AF) / sum STI(all).

(= (measure-sti-concentration)
   (let* (($af        (getAfAtoms))
          ($all-atoms (getAtomsInTypeSpace))
          ($af-sti    (foldall + (let $a (superpose $af)        (getSti $a)) 0.0))
          ($all-sti   (foldall + (let $a (superpose $all-atoms) (getSti $a)) 0.0)))
        (if (> $all-sti 0.0) (/ $af-sti $all-sti) 0.0)))

; ---- §2.1.3  Link Density -----------------------------------
; |H-links with both ends in AF| / (|AF|(|AF|-1)); 0 if |AF| < 2.
; Counted via AF-out links whose target is also in AF.

(= (measure-link-density)
   (let* (($af   (getAfAtoms))
          ($af-n (* 1.0 (size-atom $af)))
          ($max  (* $af-n (- $af-n 1.0))))
        (if (> $max 0.0)
            (let $n (* 1.0 (size-atom
                       (collapse
                          (let $src (superpose $af)
                               (let $from (get-hlinks-from $src)
                                    (let $link (superpose $from)
                                         (if (isAtomInAf (get-hlink-target $link))
                                             $link
                                             (empty))))))))
                (/ $n $max))
            0.0)))
