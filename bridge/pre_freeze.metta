; Freeze-F prefix: use exported AF as F (no re-seed / no ecan-cycles).
; Requires scenario: fx-focus, fx-objects, fx-tables, fx-cycles ignored.
!(import! &self core)
!(import! &self ecan)
!(import! &self "cognitive_synergy_io.py")

!(updateAttentionParam MAX_SPREAD_PERCENTAGE 0.4)
!(updateAttentionParam HEBBIAN_MAX_ALLOCATION_PERCENTAGE 0.1)
!(updateAttentionParam AFRentFrequency 1000.0)
!(updateAttentionParam TOPK 1.0)
!(updateAttentionParam MAX_SIZE 64.0)
!(updateAttentionParam ACC_DIV_SIZE 4.0)
!(updateAttentionParam FORGET_THRESHOLD 0.05)

!(install-incident-from-tables! (fx-tables))
!(register-all! (fx-objects))
; Do not seed or cycle — F is the snapshot AF.
!(bind! &Fseed (new-state ()))
!(change-state! &Fseed (fx-focus))
!(bind! &Fold (new-state ()))
!(change-state! &Fold (fx-focus))
!(bind! &F (new-state ()))
!(change-state! &F (fx-focus))
!(bind! &k (new-state 0))
!(change-state! &k (size-atom (get-state &F)))
!(bind! &B (new-state 10))
!(bind! &wage (new-state 200.0))
!(bind! &rngSeed (new-state 0))
!(println! (freeze-f F (get-state &F) k (get-state &k)))
