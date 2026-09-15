CREATE TABLE compte_client (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    mdp TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    date_inscription TIMESTAMP DEFAULT NOW(),
    reset_token_hash TEXT,
    reset_token_expires TIMESTAMP
);

CREATE TABLE destinations (
    id SERIAL PRIMARY KEY,
    ville VARCHAR(100) NOT NULL,
    pays VARCHAR(100) NOT NULL,
    code_iata VARCHAR(10),
    aeroport VARCHAR(150),
    image TEXT
);

CREATE TABLE vols (
    id SERIAL PRIMARY KEY,
    destination_id INTEGER NOT NULL REFERENCES destinations(id),
    date DATE NOT NULL,
    heure_depart TIME NOT NULL,
    prix NUMERIC(10,2) NOT NULL,
    compagnie VARCHAR(100)
);

CREATE TABLE hotels (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(150) NOT NULL,
    adresse VARCHAR(255),
    ville VARCHAR(100) NOT NULL,
    cp VARCHAR(20),
    pays VARCHAR(100),
    telephone VARCHAR(30),
    nombre_de_jour_a_reserver INTEGER,
    nombre_de_chambre INTEGER,
    descriptions TEXT,
    tarifs NUMERIC(10,2) NOT NULL,
    avis TEXT,
    photos TEXT,
    slug VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE reservations_hotel (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES compte_client(id),
    hotel_id INTEGER NOT NULL REFERENCES hotels(id),
    date_arrivee DATE NOT NULL,
    date_depart DATE NOT NULL,
    nombre_nuits INTEGER NOT NULL,
    nombre_adultes INTEGER NOT NULL,
    nombre_enfants INTEGER NOT NULL DEFAULT 0,
    tarif_total NUMERIC(10,2) NOT NULL,
    statut VARCHAR(20) NOT NULL DEFAULT 'Non payé',
    date_paiement TIMESTAMP,
    nom VARCHAR(100),
    prenom VARCHAR(100),
    adresse VARCHAR(255),
    ville VARCHAR(100),
    cp VARCHAR(20),
    telephone VARCHAR(30),
    email VARCHAR(255)
);

CREATE TABLE reservations_vol (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES compte_client(id),
    vol_id INTEGER NOT NULL REFERENCES vols(id),
    nombre_adultes INTEGER NOT NULL,
    nombre_enfants INTEGER NOT NULL DEFAULT 0,
    tarif_total NUMERIC(10,2) NOT NULL,
    statut VARCHAR(20) NOT NULL DEFAULT 'Non payé',
    date_paiement TIMESTAMP,
    nom VARCHAR(100),
    prenom VARCHAR(100),
    adresse VARCHAR(255),
    ville VARCHAR(100),
    cp VARCHAR(20),
    telephone VARCHAR(30),
    email VARCHAR(255)
);

CREATE TABLE formulaire_contact (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    telephone VARCHAR(30),
    email VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    date_envoi TIMESTAMP DEFAULT NOW()
);

CREATE TABLE paiements (
    id SERIAL PRIMARY KEY,
    nom_prenom VARCHAR(200) NOT NULL,
    date_de_paiement TIMESTAMP DEFAULT NOW()
);
