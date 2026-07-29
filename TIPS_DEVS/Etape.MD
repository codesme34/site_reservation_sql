0: mettre en olace un environnement virtuel et installer les dependences avec un requirements.txt ensuite python3 -m venv venv && source venv/bin/activate



1: Mettre en place le .env

--------------------------GITHUB-------------------------------------------

2: Mettre le place le .gitignore

'''
__pycache__/ : dossier que Python crée automatiquement pour stocker le bytecode compilé (.pyc) de tes fichiers .py. Généré tout seul à chaque exécution, aucun intérêt à le versionner.

*.pyc : les fichiers bytecode compilés eux-mêmes (au cas où ils traînent hors d'un __pycache__/).

.env : ton fichier de variables sensibles (mot de passe PostgreSQL, clé secrète Flask). Ne doit jamais être public.

venv/ et .venv/ : le dossier de ton environnement virtuel Python (tous les packages installés). Ça peut peser des centaines de Mo et se recrée en une commande (pip install -r requirements.txt) — donc inutile de le versionner, chacun le recrée chez soi.

instance/ : dossier que Flask utilise parfois pour stocker de la config locale ou une DB SQLite (pas ton cas ici avec PostgreSQL, mais on le laisse par sécurité, ça ne coûte rien).

*.db et *.sqlite3 : fichiers de base de données locale au format SQLite. Pas ton cas (tu es sur PostgreSQL, qui tourne en serveur externe, pas en fichier), mais c'est une bonne pratique standard à garder.
'''


3: Cree le repositories et le connecter au dossier en local
4: Initier le git : git init

''''''
git add .gitignore README
git commit -m "Init projet"
git branch -M main
git remote add origin https://github.com/codesme34/site_reservation_sql.git
git push -u origin main

'''''

--------------------------GITHUB-------------------------------------------


--------------------------DATA BASE------------------------------------------------


5: Se connecter en admin a postgre en ligne de commande : 
sudo -u postgres psql


6: Cree un utilisateur et mdp : 

CREATE USER site_reservation_user WITH PASSWORD 'mon_mdp';

Réponse attendue si ça a marché : CREATE USER ...;	CREATE ROLE

7: Créer la base de données, avec ce user comme propriétaire

CREATE DATABASE site_reservation OWNER site_reservation_user;

8: Donner tous les droits sur la base à ce user

GRANT ALL PRIVILEGES ON DATABASE site_reservation TO 
site_reservation_user;

9: Vérifier que tout existe:
\du :(display users) : liste tous les rôles/utilisateurs PostgreSQL existants sur le serveur, avec leurs attributs (superuser, capacité à créer des DB, etc.). Ça te permet de vérifier que site_reservation_user a bien été créé.


\l : (list) : liste toutes les bases de données existantes sur le serveur, avec leur propriétaire (owner), encodage, etc. Ça te permet de vérifier que site_reservation a bien été créée et que son owner est bien site_reservation_user.

\q : quitter


10 :  cree un fichier db.py pour connnecter la db a python (ne pas oublier de mettre a chaque dossier un __init__.py)


11: Si erreur clavier pour le mdp tu peux essayer : 

PGPASSWORD='AZERTY123' psql -U site_reservation_user -d site_reservation -h localhost



12: Cree les tables que on a besoin sur le site  : Compte_client etc...... 

on selection la databse cree et on fait \c site_reservation une fois dessus on cree la table: 

exemple : CREATE TABLE compte_client (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    mot_de_passe TEXT NOT NULL,
    date_inscription TIMESTAMP DEFAULT NOW()
);







----------------DATA BASE------------------------------------------------





