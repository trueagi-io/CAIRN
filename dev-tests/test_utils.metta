; Run from CAIRN/: ../PeTTa/run.sh dev-tests/test_utils.metta
; Tests the HebbianLink accessors added to tools/utils.metta.
; (Statistical functions — Pearson, Shannon, etc. — are exercised
;  indirectly through the assessment/audit tests.)

; ---- Stub metta-attention API --------------------------------
; Minimal typeSpace with three ASYMMETRIC_HEBBIAN_LINKs.
; The value field ('stub) satisfies the wildcard $_ in get-all-hlinks.

!(bind! &typeSpace (new-space))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a b) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK b c) stub))
!(add-atom &typeSpace ((ASYMMETRIC_HEBBIAN_LINK a c) stub))

(= (getMean (ASYMMETRIC_HEBBIAN_LINK a b)) 0.8)
(= (getMean (ASYMMETRIC_HEBBIAN_LINK b c)) 0.6)
(= (getMean (ASYMMETRIC_HEBBIAN_LINK a c)) 0.7)

; ---- Load module under test ----------------------------------

!(import! &self tools/utils)

; ---- Helpers -------------------------------------------------

(= (assert-eq $label $expected $actual)
   (if (== $expected $actual)
       (println! (PASS $label))
       (println! (FAIL $label expected: $expected got: $actual))))

; ---- Field accessors -----------------------------------------

!(assert-eq get-hlink-source a (get-hlink-source (ASYMMETRIC_HEBBIAN_LINK a b)))
!(assert-eq get-hlink-target b (get-hlink-target (ASYMMETRIC_HEBBIAN_LINK a b)))
!(assert-eq get-hlink-source-bc b (get-hlink-source (ASYMMETRIC_HEBBIAN_LINK b c)))
!(assert-eq get-hlink-target-bc c (get-hlink-target (ASYMMETRIC_HEBBIAN_LINK b c)))

; ---- Probability lookup --------------------------------------

!(assert-eq get-hlink-prob-ab 0.8 (get-hlink-probability a b))
!(assert-eq get-hlink-prob-bc 0.6 (get-hlink-probability b c))
!(assert-eq get-hlink-prob-ac 0.7 (get-hlink-probability a c))

; ---- get-all-hlinks ------------------------------------------

!(let $hlinks (get-all-hlinks)
   (assert-eq get-all-hlinks-count 3 (size-atom $hlinks)))
