-- Compteur des identifiants de commande (CMD-000001, CMD-000002…).
-- Une ligne insérée = un numéro attribué. AUTOINCREMENT garantit qu'un numéro
-- n'est jamais réattribué, même après suppression de lignes.

CREATE TABLE IF NOT EXISTS order_id_sequence (
    id INTEGER PRIMARY KEY AUTOINCREMENT
) STRICT;
