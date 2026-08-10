; =============================================================
; CAIRN – Cognitive synergy (coupled mve_bridge entry, B2)
;
; Pathway:
;   demo → mve → assignment           structural CIP
;              ↘ mve_bridge / this    export AF → freeze-F PLN
;
; Prefer CLI (dump once → offline grid):
;   python bridge/mve_bridge.py --export-only
;   python bridge/mve_bridge.py --offline-grid --budgets 5,10,20 --focus-cap 12
;   python bridge/mve_bridge.py --offline-grid --modes freeze-f,re-dynamics \
;       --focus-caps 6,12 --budgets 10 --feedback
;
; PeTTa defaults (mve + freeze-f, B=10, k=12):
;   ../PeTTa/run.sh cognitive_synergy.metta
;
; Standalone B1 (no CIP):
;   python bridge/run_bridge.py suite --map slice --budgets 5,10,20
; =============================================================

!(import! &self "bridge/mve_bridge.py")

!(println! (Launching CAIRN cognitive synergy — mve_bridge))
!(py-call (mve_bridge.run))
!(println! (CAIRN cognitive synergy finished))
