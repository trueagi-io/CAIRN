; Protocol: Cq∧AF filter, seed, feedback wage. Table = (Table id Inheritance legs stv stamp)

(= (table-id (Table $id $_ $_ $_ $_)) $id)
(= (table-legs (Table $_ $_ $legs $_ $_)) $legs)

(= (member? $x $ys)
   (let $hits (collapse (let $y (superpose $ys) (if (== $x $y) True (empty))))
        (if (== $hits ()) False True)))

(= (cq-af-keep $table $Q $F)
   (let $legs (table-legs $table)
        (let $qlegs (collapse (let $leg (superpose $legs)
                                   (if (== (member? $leg $Q) True) $leg (empty))))
             (let $hits (collapse (let $x (superpose $qlegs)
                                       (if (== (member? $x $F) True) True (empty))))
                  (if (== $hits ()) False True)))))

(= (filter-tables () $Q $F) ())
(= (filter-tables (cons $t $rest) $Q $F)
   (if (== (cq-af-keep $t $Q $F) True)
       (cons $t (filter-tables $rest $Q $F))
       (filter-tables $rest $Q $F)))

; Predicate is free (Inheritance for roman/slice; coupled uses Inheritance dual of Hebbian).
(= (table->sentence (Table $id $pred $legs $stv $stamp))
   (Sentence (($pred (car-atom $legs) (car-atom (cdr-atom $legs))) $stv) $stamp))

; Unbounded tables→kb (old kb-cons matched only ≤8 sentences — broke large AF filters).
(= (each-table ()) (empty))
(= (each-table (cons $t $rest))
   (superpose ($t (each-table $rest))))
(= (tables->kb $tables)
   (collapse (let $t (each-table $tables) (table->sentence $t))))

(= (count-tables () ) 0)
(= (count-tables (cons $_ $rest)) (+ 1 (count-tables $rest)))
(= (filter-kb $tables $Q $F) (tables->kb (filter-tables $tables $Q $F)))
(= (n-kept $tables $Q $F) (count-tables (filter-tables $tables $Q $F)))

(= (seed! $atom $wage)
   (let* (($_ (collapse (setAv $atom (0.0 0.0 0))))
          ($_2 (collapse (stimulate $atom $wage)))) done))
(= (seed-all! $atoms $wage)
   (let $_ (collapse (let $a (superpose $atoms) (seed! $a $wage))) done))

(= (sti-of $atom)
   (let $r (collapse (getSti $atom))
        (if (== $r ()) 0.0 (* 1.0 (car-atom $r)))))

; Drop zero-STI pad so |F| / Cq∧AF reflect real attention (not empty AV slots).
(= (positive-focus $F)
   (collapse (let $o (superpose $F)
                  (if (> (sti-of $o) 0.0) $o (empty)))))

; |Q ∩ F| / |Q| after dynamics (plan metric)
(= (query-af-overlap $Q $F)
   (let $nq (size-atom (collapse (let $q (superpose $Q) $q)))
        (let $ni (size-atom (collapse (let $q (superpose $Q)
                                           (if (== (member? $q $F) True) $q (empty)))))
             (if (== $nq 0) 0.0 (/ (* 1.0 $ni) (* 1.0 $nq))))))

; Feedback — stamp ids only. Call (fx-tables) inside (arg cons-chains don't match).
(= (legs-of $id () ) ())
(= (legs-of $id (cons $t $rest))
   (if (== (table-id $t) $id) (table-legs $t) (legs-of $id $rest)))
(= (stamp-objects $stamps)
   (collapse (let $sid (superpose $stamps)
                  (let $legs (legs-of $sid (fx-tables))
                       (let $o (superpose $legs) $o)))))
(= (wage! $objs $wage)
   (let $_ (collapse (let $o (superpose $objs) (seed! $o $wage))) done))
(= (new-in-focus $objs $F0 $F1)
   (collapse (let $o (superpose $objs)
                  (if (and (== (member? $o $F1) True) (== (member? $o $F0) False))
                      $o (empty)))))
; Proof atoms already in F / still in F after wage+cycle
(= (in-focus $objs $F)
   (collapse (let $o (superpose $objs)
                  (if (== (member? $o $F) True) $o (empty)))))
(= (sti-pairs $objs)
   (collapse (let $o (superpose $objs) ($o (sti-of $o)))))
