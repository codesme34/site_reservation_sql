# Checklist sécurité (OWASP) — à vérifier à chaque nouvelle route

À relire à chaque fois que tu crées une API : est-ce que je respecte ces règles ?

---

## Étape 1 — Injection SQL

**Le risque** : un attaquant insère du code SQL dans un champ de formulaire pour manipuler ta requête et accéder/modifier des données qu'il ne devrait pas.

**Ce qu'il ne faut PAS faire :**
```python
# JAMAIS de f-string / concaténation avec des données utilisateur
cursor.execute(f"SELECT * FROM compte_client WHERE email = '{email}'")
cursor.execute("SELECT * FROM compte_client WHERE email = '" + email + "'")
```
Avec ça, un attaquant qui tape `' OR '1'='1` dans le champ email récupère tous les comptes.

**Ce qu'il faut faire :** toujours utiliser des requêtes paramétrées avec `%s`, jamais construire la requête à la main.
```python
cursor.execute("SELECT * FROM compte_client WHERE email = %s", (email,))
```
psycopg2 échappe automatiquement la valeur — le driver s'occupe de la sécurité, pas toi.

**Checklist :**
- [ ] Aucune f-string / `.format()` / `+` avec une variable utilisateur dans une requête SQL
- [ ] Toutes les valeurs passent par `%s` + tuple de paramètres

---

## Étape 2 — Éviter le XSS (Cross-Site Scripting)

**Le risque** : un attaquant insère du code JavaScript dans une donnée (nom, avis, message de contact...) qui sera ensuite affichée à d'autres utilisateurs sans être échappée. Le script s'exécute alors dans leur navigateur (vol de session, etc.).

**Ce qu'il ne faut PAS faire :**
- Désactiver l'auto-échappement de Jinja2 (`| safe`) sur une donnée qui vient d'un utilisateur, sans validation.
- Construire du HTML côté backend en insérant une donnée utilisateur brute dans une chaîne.

**Ce qu'il faut faire :**
- Laisser Jinja2 échapper automatiquement les variables dans les templates (comportement par défaut, ne pas désactiver avec `| safe` sauf certitude absolue que la donnée est sûre).
- Si l'API renvoie du JSON (cas Postman actuel), le risque XSS est côté front plus tard, pas maintenant — mais garder le réflexe : jamais de HTML généré à partir d'une entrée utilisateur non échappée.

**Checklist :**
- [ ] Pas de `| safe` sur une donnée provenant d'un formulaire utilisateur
- [ ] Pas de construction de HTML à la main avec des données utilisateur

---

## Étape 3 — CSRF (Cross-Site Request Forgery)

**Le risque** : un attaquant piège un utilisateur déjà connecté (session active) pour lui faire exécuter une action à son insu (changer mot de passe, faire une réservation...) via un lien/formulaire malveillant sur un autre site.

**Ce qu'il faut faire :**
- Utiliser un token CSRF sur tous les formulaires qui modifient des données (POST/PUT/DELETE), une fois le front en place (ex: `Flask-WTF` gère ça automatiquement).
- Vérifier que les cookies de session ont l'attribut `SameSite` correctement configuré.
- Pour une API pure (Postman/JSON avec token d'auth plutôt que cookie de session), le risque CSRF est réduit mais pas nul si tu mélanges cookie de session + API.

**Checklist :**
- [ ] Les routes qui modifient des données (POST/PUT/DELETE) sont protégées par CSRF si elles reposent sur des cookies de session
- [ ] Pas de action sensible déclenchée par une simple requête GET

---

## Étape 4 — Bcrypt (mots de passe)

**Le risque** : stocker un mot de passe en clair ou avec un hash faible (MD5, SHA1 sans sel) permet à quiconque accède à la base de récupérer tous les mots de passe.

**Ce qu'il ne faut PAS faire :**
```python
# Jamais en clair
mdp = request.form['password']
cursor.execute("INSERT INTO compte_client (mot_de_passe) VALUES (%s)", (mdp,))
```

**Ce qu'il faut faire :**
```python
mdp_hash = bcrypt.hashpw(mdp.encode('utf-8'), bcrypt.gensalt())
# stocker mdp_hash (colonne TEXT), jamais le mot de passe original

# à la vérification (login) :
bcrypt.checkpw(mdp_saisi.encode('utf-8'), mdp_hash_stocke)
```

**Checklist :**
- [ ] Le mot de passe est toujours encodé en bytes (`.encode('utf-8')`) avant `bcrypt.hashpw`
- [ ] Un `salt` différent est généré à chaque hash (`bcrypt.gensalt()`, jamais un sel fixe)
- [ ] Le mot de passe en clair n'est jamais stocké, jamais loggé (`print()`), jamais renvoyé dans une réponse JSON

---

## Étape 5 — Rate limiting (anti brute-force / anti spam)

**Le risque** : sans limite, un attaquant peut appeler une route des milliers de fois par seconde — pour deviner un mot de passe par force brute sur `/login`, pour créer des milliers de faux comptes, ou juste pour surcharger ton serveur (déni de service).

**Ce qu'il faut faire :**
- Ajouter une limite de nombre de requêtes par IP/par utilisateur sur les routes sensibles, en particulier `/login` et `/create_login`. En Flask, la librairie standard est `Flask-Limiter` :
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(app=app, key_func=get_remote_address)

@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    ...
```
- Prioriser les routes qui touchent à l'authentification ou à l'écriture en base (login, création de compte, réservation, paiement).

**Checklist :**
- [ ] Les routes `/login` et `/create_login` ont une limite de requêtes par IP
- [ ] Les routes d'écriture sensibles (réservation, paiement) sont aussi limitées

---

## Étape 6 — Validation des entrées

**Le risque** : faire confiance aux données envoyées par le client (Postman aujourd'hui, un attaquant demain) sans vérifier leur format peut casser ton app ou insérer des données invalides en base.

**Ce qu'il faut faire :**
- Vérifier que les champs attendus existent avant de les utiliser (`data.get('email')` plutôt que `data['email']` qui plante si absent, puis contrôler que la valeur n'est pas `None`).
- Valider le format (email bien formé, mot de passe avec une longueur minimale, dates cohérentes...).
- Ne jamais faire confiance à un champ "prix" ou "montant" envoyé par le client pour un paiement — recalculer le prix côté serveur à partir des données de la base, jamais depuis ce que le client prétend payer.

**Checklist :**
- [ ] Chaque champ obligatoire est vérifié avant utilisation (présence + type + format)
- [ ] Aucun prix/montant sensible n'est accepté tel quel depuis le client sans revérification serveur

---

## Étape 7 — Contrôle d'accès (IDOR)

**Le risque** : IDOR = Insecure Direct Object Reference. Un utilisateur connecté modifie l'`id` dans l'URL (ex: `/reservation/12` → `/reservation/13`) et accède aux données d'un autre utilisateur, simplement parce que la route ne vérifie pas le propriétaire de la ressource.

**Ce qu'il faut faire :**
- Sur chaque route qui lit/modifie/supprime une ressource par id, vérifier que cette ressource appartient bien à l'utilisateur connecté (`WHERE id = %s AND client_id = %s`), pas juste `WHERE id = %s`.

**Checklist :**
- [ ] Toute route `/xxx/<id>` vérifie que la ressource appartient à l'utilisateur courant, pas juste qu'elle existe

---

## Étape 8 — Gestion des secrets et des erreurs

**Le risque** : exposer des informations sensibles via le `.env` mal protégé, ou via des messages d'erreur trop détaillés qui aident un attaquant.

**Ce qu'il faut faire :**
- `.env` toujours dans `.gitignore`, jamais commité.
- En production, désactiver le mode debug de Flask (`debug=False`) — le mode debug affiche la stack trace complète (chemins de fichiers, code source) à qui déclenche une erreur.
- Ne jamais renvoyer l'erreur brute de psycopg2/Python dans la réponse JSON au client — logger l'erreur côté serveur, renvoyer un message générique côté client.

**Checklist :**
- [ ] `app.run(debug=True)` n'est utilisé qu'en développement local, jamais en prod
- [ ] Les erreurs internes ne sont jamais renvoyées telles quelles dans la réponse HTTP

---

## Rappel général à chaque nouvelle route

- [ ] Toutes les entrées utilisateur (`request.get_json()`, `request.form`) sont-elles utilisées uniquement via des requêtes paramétrées ?
- [ ] Les routes sensibles sont-elles protégées par une authentification (`@login_required` ou équivalent) ?
- [ ] Les erreurs ne révèlent-elles pas d'info sensible (ex: ne pas dire "email inexistant" vs "mot de passe incorrect" séparément — préférer un message générique "identifiants invalides")
- [ ] Le mot de passe/token n'apparaît jamais dans un `print()`, un log, ou une réponse JSON
