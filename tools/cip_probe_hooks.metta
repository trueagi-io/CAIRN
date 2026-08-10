; =============================================================
; Mid-run PLN probe hooks (only via mve_pln_probe inject).
; Requires: bridge/export_snapshot.py, bridge/cip_probe.py, tools/bridge_export
; =============================================================

; Soft-fail: probe errors must not abort CIP (Python catches).
; Returns wage atom list (may be empty) for optional stimulate.
(= (maybe-pln-probe! $cip-index)
   (let $want (py-call (cip_probe.should_probe $cip-index))
        (if (== $want True)
            (py-call (cip_probe.run_probe
                        $cip-index
                        (getAfAtoms)
                        (bridge-export-sti (getAfAtoms))
                        (bridge-export-edges)))
            ())))

; Stimulate each atom in a flat list returned from Python (closed loop).
(= (wage-probe-atom! $a $w)
   (let* (($_ (collapse (setAv $a (0.0 0.0 0))))
          ($_2 (collapse (stimulate $a $w))))
        done))

(= (wage-probe-atoms-acc! () $w) done)
(= (wage-probe-atoms-acc! ($a $rest) $w)
   (let* (($_ (wage-probe-atom! $a $w))
          ($_2 (wage-probe-atoms-acc! $rest $w)))
        done))

; $atoms may be Python list or MeTTa expression — superpose if list-like via py.
(= (apply-probe-wages! $atoms $wage)
   (if (== $atoms ())
       done
       (let $_ (collapse (let $a (superpose $atoms) (wage-probe-atom! $a $wage)))
            done)))

; Full hook: probe then wage if list non-empty.
(= (pln-probe-and-maybe-wage! $cip-index $wage)
   (let $atoms (maybe-pln-probe! $cip-index)
        (if (== $atoms ())
            done
            (let $_ (apply-probe-wages! $atoms $wage)
                 (println! (pln-probe-wage cip $cip-index atoms $atoms wage $wage))))))
