; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_timeseries.metta
;
; Stubs metta-attention API with spaces so values can be updated
; between recordings without non-deterministic rule overlap.

; ---- Stub metta-attention API --------------------------------

; record-cip-series reads the value cell in one pass, not getSti/getLti.
!(bind! &typeSpace (new-space))
!(add-atom &typeSpace (a ((AV 8.0 0.9 0) (Bin 0))))
!(add-atom &typeSpace (b ((AV 3.0 0.4 0) (Bin 0))))

(= (set-sample! $atom $oldsti $oldlti $sti $lti)
   (let* (($_ (remove-atom &typeSpace ($atom ((AV $oldsti $oldlti 0) (Bin 0))))))
        (add-atom &typeSpace ($atom ((AV $sti $lti 0) (Bin 0))))))

; ---- Load module under test ----------------------------------

!(import! &self tools/timeseries)

; ---- Helpers -------------------------------------------------

(= (assert-eq $label $expected $actual)
   (if (== $expected $actual)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

; ---- CIP 1: record initial values ---------------------------

!(record-cip-series)

!(assert-eq sti-a-after-cip1 (cons 8.0 ()) (get-sti-series a))
!(assert-eq sti-b-after-cip1 (cons 3.0 ()) (get-sti-series b))
!(assert-eq lti-a-after-cip1 (cons 0.9 ()) (get-lti-series a))

; ---- CIP 2: shift attention, record again -------------------

!(set-sample! a 8.0 0.9 9.5 0.9)
!(set-sample! b 3.0 0.4 2.0 0.4)
!(record-cip-series)

; Expected: oldest-first, so cip-1 value then cip-2 value
!(assert-eq sti-a-after-cip2 (cons 8.0 (cons 9.5 ())) (get-sti-series a))
!(assert-eq sti-b-after-cip2 (cons 3.0 (cons 2.0 ())) (get-sti-series b))
