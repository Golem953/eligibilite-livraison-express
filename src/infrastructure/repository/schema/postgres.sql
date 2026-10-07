-- Schéma PostgreSQL (CI et prod). Mêmes règles que sqlite.sql, avec les types
-- natifs de PostgreSQL.

CREATE TABLE IF NOT EXISTS orders (
    order_id                VARCHAR(50)      PRIMARY KEY CHECK (length(order_id) >= 1),
    order_date              TIMESTAMPTZ      NOT NULL,
    hour                    SMALLINT         NOT NULL CHECK (hour BETWEEN 0 AND 23),
    day_of_week             SMALLINT         NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    weekend                 BOOLEAN          NOT NULL,
    distance_km             DOUBLE PRECISION NOT NULL CHECK (distance_km >= 0),
    order_value_eur         DOUBLE PRECISION NOT NULL CHECK (order_value_eur >= 0),
    weight_kg               DOUBLE PRECISION NOT NULL CHECK (weight_kg >= 0),
    stock_available         BOOLEAN          NOT NULL,
    preparation_time_min    DOUBLE PRECISION NOT NULL CHECK (preparation_time_min >= 0),
    carrier_capacity        DOUBLE PRECISION NOT NULL
                                             CHECK (carrier_capacity BETWEEN 0 AND 1),
    weather                 VARCHAR(20)      NOT NULL
                                             CHECK (weather IN ('normal', 'pluie',
                                                                'neige', 'orage')),
    delivery_zone           VARCHAR(20)      NOT NULL
                                             CHECK (delivery_zone IN ('centre',
                                                                      'proche_banlieue',
                                                                      'banlieue',
                                                                      'rurale')),
    customer_type           VARCHAR(20)      NOT NULL
                                             CHECK (customer_type IN ('standard',
                                                                      'premium')),
    status                  VARCHAR(20)      NOT NULL
                                             CHECK (status IN ('recue', 'predite',
                                                               'labellisee')),
    predicted_eligible      BOOLEAN,
    eligibility_probability DOUBLE PRECISION CHECK (eligibility_probability BETWEEN 0 AND 1),
    model_version           VARCHAR(50)      CHECK (length(model_version) >= 1),
    predicted_at            TIMESTAMPTZ,
    real_label              BOOLEAN,
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
);

CREATE INDEX IF NOT EXISTS idx_orders_status_date ON orders (status, order_date);
