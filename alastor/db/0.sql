CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE migrations (
    id integer PRIMARY KEY NOT NULL
);

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    email text NOT NULL UNIQUE,
    pwd text NOT NULL,
    obj jsonb NOT NULL DEFAULT '{}' ::jsonb
);

CREATE INDEX idxginlevel ON users USING gin ((obj -> 'level'));

CREATE TABLE tournaments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    date tstzrange,
    obj jsonb NOT NULL DEFAULT '{}' ::jsonb
);
