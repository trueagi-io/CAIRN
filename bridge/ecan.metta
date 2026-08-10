; Full ECAN agent stack (read-only metta-attention). Spaces: &incident &hebb.
!(import! &self ../metta-attention/attention-bank/bank/stochastic-importance-diffusion/stochastic-importance-diffusion)
!(import! &self ../metta-attention/attention/RentCollectionAgent/RentCollectionBaseAgent/RentCollectionBaseAgent)
!(import! &self ../metta-attention/attention/RentCollectionAgent/AFRentCollectionAgent/AFRentCollectionAgent)
!(import! &self ../metta-attention/attention/RentCollectionAgent/WARentCollectionAgent/WARentCollectionAgent)
!(import! &self ../metta-attention/attention/ImportanceDiffusionAgent/ImportanceDiffusionBase/ImportanceDiffusionBase)
!(import! &self "getelement.py")
!(import! &self ../metta-attention/attention/ImportanceDiffusionAgent/AFImportanceDiffusionAgent/AFImportanceDiffusionAgent)
!(import! &self ../metta-attention/attention/ImportanceDiffusionAgent/WAImportanceDiffusionAgent/WAImportanceDiffusionAgent)
!(import! &self ../metta-attention/attention/HebbianUpdatingAgent/HebbianUpdatingAgent)
!(import! &self ../metta-attention/attention/HebbianCreationAgent/HebbianCreationAgent)
!(import! &self ../metta-attention/attention/ForgettingAgent/ForgettingAgent)

!(bind! &incident (new-space))
!(bind! &hebb (new-space))

; One dynamics step: AF/WA rent+diffuse → hebbian → forget (capacity prune)
; forgettingAgent-Run ignores $space; uses TypeSpace + FORGET_THRESHOLD / MAX_SIZE.
(= (ecan-cycle!)
   (let* (($_ar (AFRentCollectionAgent-run))
          ($_ad (AFImportanceDiffusionAgent-Run &incident &hebb))
          ($_wr (WARentCollectionAgent-Run))
          ($_wd (WAImportanceDiffusionAgent-Run &incident))
          ($_h (HebbianCreationAgent-Run &hebb))
          ($_u (HebbianUpdatingAgent-Run &hebb))
          ($_f (forgettingAgent-Run &hebb)))
        done))

(= (ecan-cycles! $n)
   (if (<= $n 0)
       done
       (let* (($_ (ecan-cycle!))
              ($_2 (ecan-cycles! (- $n 1))))
            done)))

; Register V in AV bank (zero STI) so diffusion targets exist
(= (register-all! $objs)
   (let $_ (collapse (let $o (superpose $objs)
                          (collapse (setAv $o (0.0 0.0 0)))))
        done))

; Auto incident graph from table legs (undirected). Entry = (node (n1 n2 ...)).
(= (table-edge (Table $_ Inheritance $legs $_ $_))
   ((car-atom $legs) (car-atom (cdr-atom $legs))))
(= (tables-edges () ) ())
(= (tables-edges (cons $t $rest))
   (cons (table-edge $t) (tables-edges $rest)))

(= (install-neighbor-entry ($n $ns))
   (add-atom &incident ($n $ns)))
(= (install-neighbor-list () ) done)
(= (install-neighbor-list (cons $e $rest))
   (let* (($_ (install-neighbor-entry $e))
          ($_2 (install-neighbor-list $rest)))
        done))
; Python returns [[node, [n...]], ...] — superpose installs each row
(= (install-incident-from-tables! $tables)
   (let $rows (py-call (cognitive_synergy_io.neighbors_from_edges (tables-edges $tables)))
        (let $_ (collapse (let $e (superpose $rows) (install-neighbor-entry $e)))
             done)))
