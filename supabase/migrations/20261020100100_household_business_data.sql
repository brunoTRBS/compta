-- Migration 013b : le foyer devient une activité à part entière (étape 2/2)
-- Exécuter dans une exécution SÉPARÉE, après la 013a (voir son en-tête).
--
-- Reclasse sous l'activité « household » les opérations et les règles qui étaient
-- marquées is_household. La colonne is_household est conservée (l'app ne la lit plus)
-- pour pouvoir revenir en arrière ; elle sera supprimée plus tard.

UPDATE transactions
SET business_id = 'household'
WHERE is_household;

UPDATE categorization_rules
SET business_id = 'household'
WHERE is_household;
