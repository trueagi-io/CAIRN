; Import AFTER scenarios/*_pln (lib_pln loaded)
(= (pln-solved ()) False)
(= (pln-solved ($tv $ev)) True)
(= (pln-confidence ()) 0.0)
(= (pln-confidence ((stv $f $c) $ev)) $c)
(= (pln-stamps ()) ())
(= (pln-stamps ((stv $f $c) $ev)) $ev)
(= (pln-query $kb $term $steps)
   (if (== $kb ()) () (PLN.Query $kb $term $steps)))
(= (proof-objects $ans)
   (if (== $ans ()) () (stamp-objects (pln-stamps $ans))))

; Timed PLN.Query: wall-clock ms around inference only (not filter-kb build).
; Requires cognitive_synergy_io already imported (pre / pre_freeze).
(= (pln-query-timed $kb $term $steps)
   (let $t0 (py-call (cognitive_synergy_io.wall_ms))
        (let $ans (pln-query $kb $term $steps)
             (let $ms (py-call (cognitive_synergy_io.elapsed_ms $t0))
                  ($ans $ms)))))
