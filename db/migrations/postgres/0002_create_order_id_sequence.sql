-- Compteur des identifiants de commande (CMD-000001, CMD-000002…).
-- Une ligne insérée = un numéro attribué ; une identité n'est jamais réattribuée.

CREATE TABLE IF NOT EXISTS order_id_sequence (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
);
