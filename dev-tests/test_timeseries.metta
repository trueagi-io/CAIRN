; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_timeseries.metta
;
; Stubs metta-attention API with spaces so values can be updated
; between recordings without non-deterministic rule overlap.

; ---- Stub metta-attention API --------------------------------

!(bind! &stub-sti (new-space))
!(bind! &stub-lti (new-space))

!(add-atom &stub-sti (sti a 8.0))
!(add-atom &stub-sti (sti b 3.0))
!(add-atom &stub-lti (lti a 0.9))
!(add-atom &stub-lti (lti b 0.4))

(= (getAtomsInTypeSpace) (a b))
(= (getSti $atom) (match &stub-sti (sti $atom $val) $val))
(= (getLti $atom) (match &stub-lti (lti $atom $val) $val))

; ---- Load module under test ----------------------------------

!(import! &self tools/timeseries)

; ---- Helpers -------------------------------------------------

(= (assert-eq $label $expected $actual)
   (if (== $expected $actual)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

(= (update-sti! $atom $old $new)
   (let* (($_ (remove-atom &stub-sti (sti $atom $old))))
        (add-atom &stub-sti (sti $atom $new))))

; ---- CIP 1: record initial values ---------------------------

!(record-cip-series)

!(assert-eq sti-a-after-cip1 (cons 8.0 ()) (get-sti-series a))
!(assert-eq sti-b-after-cip1 (cons 3.0 ()) (get-sti-series b))
!(assert-eq lti-a-after-cip1 (cons 0.9 ()) (get-lti-series a))

; ---- CIP 2: shift attention, record again -------------------

!(update-sti! a 8.0 9.5)
!(update-sti! b 3.0 2.0)

!(record-cip-series)

; Expected: oldest-first, so cip-1 value then cip-2 value
!(assert-eq sti-a-after-cip2 (cons 8.0 (cons 9.5 ())) (get-sti-series a))
!(assert-eq sti-b-after-cip2 (cons 3.0 (cons 2.0 ())) (get-sti-series b))
