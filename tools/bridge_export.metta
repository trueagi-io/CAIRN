; =============================================================
; AF + Hebbian dump for coupled workshop (B2 end-of-run + shared with B3).
; Python: export_snapshot.write_attention_snapshot (canonical).
;
; PeTTa: always bind before superpose when scanning hlinks.
; Edges: AF-incident only (from-af ∪ to-af) — O(|AF|·degree).
; =============================================================

(= (bridge-hlink-edge (ASYMMETRIC_HEBBIAN_LINK $s $t))
   ($s $t (get-hlink-probability $s $t)))

(= (bridge-export-edges-from-af)
   (let $af (getAfAtoms)
        (collapse
           (let $src (superpose $af)
                (let $from-src (get-hlinks-from $src)
                     (let $link (superpose $from-src)
                          (bridge-hlink-edge $link)))))))

(= (bridge-export-edges-to-af)
   (let $af (getAfAtoms)
        (collapse
           (let $tgt (superpose $af)
                (let $to-tgt (get-hlinks-to $tgt)
                     (let $link (superpose $to-tgt)
                          (bridge-hlink-edge $link)))))))

(= (bridge-export-edges)
   (union-atom (bridge-export-edges-from-af) (bridge-export-edges-to-af)))

(= (bridge-sti-of $a)
   (let $r (collapse (getSti $a))
        (if (== $r ()) 0.0 (* 1.0 (car-atom $r)))))

(= (bridge-export-sti $atoms)
   (collapse (let $a (superpose $atoms) ($a (bridge-sti-of $a)))))

; Shared attention export (schedule=end). Used by mve_bridge --export-only tail.
; Args: path source af sti edges schedule cip max_nodes max_edges
(= (export-bridge-snapshot-force! $out-dir $source)
   (py-call (export_snapshot.write_attention_snapshot
               (py-call (export_snapshot.end_snapshot_path $out-dir))
               $source
               (getAfAtoms)
               (bridge-export-sti (getAfAtoms))
               (bridge-export-edges)
               "end"
               ()
               80 200)))
