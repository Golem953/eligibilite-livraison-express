-- Schéma SQLite (dev). Règles de rigueur imposées par l'ADR-0001 :
-- table STRICT, aucun type ANY, booléens / dates / énumérations / longueurs
-- contrôlés par des CHECK. Doit refuser au moins tout ce que refuse postgres.sql.

CREATE TABLE IF NOT EXISTS orders (
    order_id                TEXT    PRIMARY KEY NOT NULL
                                    CHECK (length(order_id) BETWEEN 1 AND 50),
    -- Dates : texte ISO 8601 en UTC, à largeur fixe (voir SqliteConnector).
    order_date              TEXT    NOT NULL
                                    CHECK (order_date LIKE '____-__-__T__:__:__.______+00:00'
                                           AND datetime(order_date) IS NOT NULL),
    hour                    INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    day_of_week             INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    weekend                 INTEGER NOT NULL CHECK (weekend IN (0, 1)),
    distance_km             REAL    NOT NULL CHECK (distance_km >= 0),
    order_value_eur         REAL    NOT NULL CHECK (order_value_eur >= 0),
    weight_kg               REAL    NOT NULL CHECK (weight_kg >= 0),
    stock_available         INTEGER NOT NULL CHECK (stock_available IN (0, 1)),
    preparation_time_min    REAL    NOT NULL CHECK (preparation_time_min >= 0),
    carrier_capacity        REAL    NOT NULL CHECK (carrier_capacity BETWEEN 0 AND 1),
    weather                 TEXT    NOT NULL
                                    CHECK (weather IN ('normal', 'pluie', 'neige', 'orage')),
    delivery_zone           TEXT    NOT NULL
                                    CHECK (delivery_zone IN ('centre', 'proche_banlieue',
                                                             'banlieue', 'rurale')),
    customer_type           TEXT    NOT NULL
                                    CHECK (customer_type IN ('standard', 'premium')),
    status                  TEXT    NOT NULL
                                    CHECK (status IN ('recue', 'predite', 'labellisee')),
    predicted_eligible      INTEGER CHECK (predicted_eligible IN (0, 1)),
    eligibility_probability REAL    CHECK (eligibility_probability BETWEEN 0 AND 1),
    model_version           TEXT    CHECK (length(model_version) BETWEEN 1 AND 50),
    predicted_at            TEXT
                                    CHECK (predicted_at LIKE '____-__-__T__:__:__.______+00:00'
                                           AND datetime(predicted_at) IS NOT NULL),
    real_label              INTEGER CHECK (real_label IN (0, 1)),
    -- Cohérence entre le statut et les colonnes remplies.
    CHECK (
        (status = 'recue'
            AND predicted_eligible IS NULL AND eligibility_probability IS NULL
            AND model_version IS NULL AND predicted_at IS NULL
            AND real_label IS NULL)
        OR (status = 'predite'
            AND predicted_eligible IS NOT NULL AND eligibility_probability IS NOT NULL
            AND model_version IS NOT NULL AND predicted_at IS NOT NULL
            AND real_label IS NULL)
        OR (status = 'labellisee'
            AND predicted_eligible IS NOT NULL AND eligibility_probability IS NOT NULL
            AND model_version IS NOT NULL AND predicted_at IS NOT NULL
            AND real_label IS NOT NULL)
    )
) STRICT;

CREATE INDEX IF NOT EXISTS idx_orders_status_date ON orders (status, order_date);
