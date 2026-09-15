from flask import Flask, request, render_template,redirect,url_for,jsonify,abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import session
from flask_wtf import CSRFProtect
from psycopg2 import errors
from Database.db import get_connection
from flask_login import LoginManager,UserMixin,logout_user,login_user,login_required,current_user
import bcrypt
import os
from psycopg2.extras import RealDictCursor
import random
import datetime
from datetime import timedelta
import secrets
import hashlib
from email_utils import send_reset_email

# admin avec delete , put , insert, delete hotel avec et sans frameworks,
# ameliorer le formulaire
# inclusitvite,navigation clavier
# parler des alt pour le front
# penser au gens qui sont dixelitique, non voyant etc ...
# utiliser du js pour du carousel par exemple....
# proteger du spam
#parle du http et https avec lets encrypts


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

csrf = CSRFProtect(app)
limiter = Limiter(app=app, key_func=get_remote_address)


@app.errorhandler(429)
def ratelimit_handler(e):
    target = request.referrer or url_for('home')
    separator = '&' if '?' in target else '?'
    return redirect(f"{target}{separator}rate_limited=1")


# "signe et sécurise les cookies de session — mettre dans un fichier .env en production" 
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login_page" #si la personne essaie d'acceder a la page mais n'est pas connecte redirige sur la page login


class User(UserMixin):
    # user_row : dictionnaire (RealDictCursor), jamais un tuple positionnel -
    # evite tout risque de melanger les colonnes si une requete change d'ordre entre-temps.
    def __init__(self, user_row):
        self.id = str(user_row['id'])
        self.nom = user_row['nom']
        self.prenom = user_row['prenom']
        self.email = user_row['email']
        self.is_admin = bool(user_row.get('is_admin', False))



@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id, nom, prenom, email, is_admin FROM compte_client WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user)
    return None


def admin_required(f):
    """Autorise uniquement les comptes avec is_admin = True.
    Different de login_required : ici l'utilisateur peut etre connecte
    mais ne pas avoir le droit d'acceder a la ressource (403), pas juste redirige vers /login."""
    from functools import wraps

    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            if request.method != 'GET':
                return jsonify({"error": "Accès réservé aux administrateurs."}), 403
            return render_template('403.html'), 403
        return f(*args, **kwargs)
    return wrapper

@app.route("/admin/comptes", methods=['GET'])
@admin_required
def admin_comptes():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT id, nom, prenom, email, is_admin, date_inscription
            FROM compte_client
            ORDER BY date_inscription DESC NULLS LAST, id DESC
        """)
        comptes = cursor.fetchall()
        return render_template('admin_comptes.html', comptes=comptes)
    finally:
        cursor.close()
        conn.close()


def _valider_champs_compte(data, password_required):
    """Validation centralisee (whitelist explicite - jamais de mass assignment).
    Renvoie (nom, prenom, email, password_ou_None, is_admin, erreur_ou_None)."""
    nom = (data.get('nom') or '').strip()
    prenom = (data.get('prenom') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    is_admin = data.get('is_admin') in (True, 'true', 'on', '1', 1)

    if not nom or not prenom or not email:
        return None, None, None, None, None, "Nom, prénom et email sont obligatoires."

    if '@' not in email or '.' not in email.split('@')[-1]:
        return None, None, None, None, None, "Adresse email invalide."

    if password_required and len(password) < 8:
        return None, None, None, None, None, "Le mot de passe doit contenir au moins 8 caractères."

    if password and not password_required and len(password) < 8:
        return None, None, None, None, None, "Le mot de passe doit contenir au moins 8 caractères."

    return nom, prenom, email, (password or None), is_admin, None


@app.route("/admin/api/comptes", methods=['POST'])
@admin_required
@limiter.limit('20 per minute')
def admin_comptes_create():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json(silent=True) or request.form

        nom, prenom, email, password, is_admin_flag, erreur = _valider_champs_compte(data, password_required=True)
        if erreur:
            return jsonify({"error": erreur}), 400

        hash_pwd = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        cursor.execute(
            "INSERT INTO compte_client (nom, prenom, email, mdp, is_admin) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (nom, prenom, email, hash_pwd, is_admin_flag)
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({"success": True, "id": new_id}), 201

    except errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "Cette adresse mail est déjà utilisée par un autre compte."}), 409

    finally:
        cursor.close()
        conn.close()


@app.route("/admin/api/comptes/<int:compte_id>", methods=['PUT'])
@admin_required
@limiter.limit('30 per minute')
def admin_comptes_update(compte_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json(silent=True) or request.form

        nom, prenom, email, password, is_admin_flag, erreur = _valider_champs_compte(data, password_required=False)
        if erreur:
            return jsonify({"error": erreur}), 400

        # un admin ne peut pas se retirer lui-meme ses droits depuis cette page
        # (protection anti-lockout : il faut qu'un AUTRE admin le fasse)
        if str(compte_id) == current_user.id and not is_admin_flag:
            return jsonify({"error": "Vous ne pouvez pas retirer vos propres droits administrateur."}), 400

        if password:
            hash_pwd = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute(
                "UPDATE compte_client SET nom = %s, prenom = %s, email = %s, is_admin = %s, mdp = %s WHERE id = %s",
                (nom, prenom, email, is_admin_flag, hash_pwd, compte_id)
            )
        else:
            cursor.execute(
                "UPDATE compte_client SET nom = %s, prenom = %s, email = %s, is_admin = %s WHERE id = %s",
                (nom, prenom, email, is_admin_flag, compte_id)
            )

        if cursor.rowcount == 0:
            conn.rollback()
            return jsonify({"error": "Compte introuvable."}), 404

        conn.commit()
        return jsonify({"success": True}), 200

    except errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "Cette adresse mail est déjà utilisée par un autre compte."}), 409

    finally:
        cursor.close()
        conn.close()


@app.route("/admin/api/comptes/<int:compte_id>", methods=['DELETE'])
@admin_required
@limiter.limit('10 per minute')
def admin_comptes_delete(compte_id):
    if str(compte_id) == current_user.id:
        return jsonify({"error": "Vous ne pouvez pas supprimer votre propre compte depuis cette page. Utilisez votre profil."}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # pas de ON DELETE CASCADE en base : on supprime d'abord les reservations liees
        cursor.execute("DELETE FROM reservations_hotel WHERE client_id = %s", (compte_id,))
        cursor.execute("DELETE FROM reservations_vol WHERE client_id = %s", (compte_id,))
        cursor.execute("DELETE FROM compte_client WHERE id = %s", (compte_id,))

        if cursor.rowcount == 0:
            conn.rollback()
            return jsonify({"error": "Compte introuvable."}), 404

        conn.commit()
        return jsonify({"success": True}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Erreur lors de la suppression du compte."}), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/")
def home():

   
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try : 
        cursor.execute("SELECT * FROM hotels")
        hot = cursor.fetchall()

        cursor.execute("""
        SELECT vols.id, destinations.ville, destinations.pays, destinations.code_iata,
            destinations.aeroport, destinations.image,
            vols.date, vols.heure_depart, vols.prix, vols.compagnie
        FROM vols
        JOIN destinations ON vols.destination_id = destinations.id""")



        vol_s = cursor.fetchall()
        list_hotels = hot
        list_vols = vol_s



        hotel_ran = random.sample(list_hotels,12)
        vol_ran =random.sample(list_vols,12)

        return render_template('index.html',hotels= hotel_ran,vols= vol_ran)

    finally: 
        cursor.close()
        conn.close()



@app.route("/search", methods=["POST"])
@limiter.limit('20 per minute')
def search():

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        type_recherche = request.form['type']

        if type_recherche == 'hotel':
            destination = request.form['destination_h']
            cursor.execute("SELECT * FROM hotels WHERE ville = %s", (destination,))
            resultats = cursor.fetchall()

        else:
            destination = request.form['destination_v']
            cursor.execute("""
                SELECT destinations.*, vols.id, vols.date, vols.heure_depart, vols.prix, vols.compagnie
                FROM vols
                JOIN destinations ON vols.destination_id = destinations.id
                WHERE destinations.pays = %s
            """, (destination,))

            resultats = cursor.fetchall()

        return render_template('recherche.html', resultats=resultats, type=type_recherche)

    except KeyError:
        return redirect(url_for('home'))

    finally:
        cursor.close()
        conn.close()


@app.route("/hotels",methods= ['GET'])
def hotels():

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM hotels")

    return render_template('hotels.html', hotels=cursor.fetchall())        


@app.route("/vols_E", methods=['GET'])
def vols():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""SELECT vols.id, destinations.ville, destinations.pays, destinations.code_iata,
                                  destinations.aeroport, destinations.image,
                                  vols.date, vols.heure_depart, vols.prix, vols.compagnie
                           FROM vols
                           JOIN destinations ON vols.destination_id = destinations.id""")
        return render_template('vols.html', vols=cursor.fetchall())
    finally:
        cursor.close()
        conn.close()



@app.route("/contact", methods=['GET','POST'])
@limiter.limit('3 per minute', methods=['POST'])
def contact():

    conn = get_connection() # connect la db 
    cursor = conn.cursor() # execute les requetes sql


    if request.method == "POST":

        try :     
            
            nom = request.form["nom"]
            prenom = request.form['prenom']
            tel = request.form['tel']
            mail = request.form['mail']
            message = request.form['message']

            cursor.execute(
                        "INSERT INTO formulaire_contact (nom, prenom, telephone, email, message) VALUES (%s, %s, %s, %s,%s)",
                        (nom, prenom, tel,mail,message))
            
            conn.commit()

            return render_template('contact.html', success=True)

        except KeyError:
            conn.rollback()
            return render_template('contact.html'), 400
        finally:
            cursor.close()
            conn.close()

    else:
        return render_template('contact.html')


#------------------Route contact----------------
@app.route("/thankyou",methods= ['GET'])
def success ():
    type_confirmation = request.args.get('type', 'contact')
    return render_template('thankyou.html', type=type_confirmation)
    


@app.route("/create_login",methods=['POST','GET'])
@limiter.limit('550 per minute',methods=['POST'])
def creation_compte():

    conn = get_connection() # connect la db 
    cursor = conn.cursor() # execute les requetes sql

    if request.method == 'POST':
        

        try : 

            nom_user = request.form['nom']
            prenom_user = request.form['prenom']
            mail_user = request.form['email']
            pwd_user = request.form['password']
            confirm_pwd_user = request.form['confirm_password']

            if pwd_user != confirm_pwd_user:
                return render_template('creation_compte.html', password_mismatch=True,
                                        nom=nom_user, prenom=prenom_user, email=mail_user), 400

            hash_pwd = bcrypt.hashpw(pwd_user.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


            # attention a bien mettre le parametre '%s' pour eviter les attaques jamais mettre de f'string (f'insert to .....')
            cursor.execute(
            "INSERT INTO compte_client (nom, prenom, email, mdp) VALUES (%s, %s, %s, %s)",
            (nom_user, prenom_user, mail_user,hash_pwd))

            conn.commit()

            return redirect(url_for('login_page')) 

        except KeyError:
            conn.rollback() # lr rollback annule la creation en cours en cas d'erreur — sans ça, la connexion reste dans un état "planté" et la prochaine requête sur cette connexion échouerait aussi.
            return render_template('creation_compte.html'), 400

        except errors.UniqueViolation:
            conn.rollback()
            return render_template('creation_compte.html', email_exists=True,
                                    nom=nom_user, prenom=prenom_user, email=mail_user), 409


        finally:
            cursor.close()
            conn.close()
        
    else:
        return render_template('creation_compte.html')

    

@app.route("/login", methods=["GET", "POST"])
@limiter.limit('5 per minute', methods=['POST'])
def login_page():

    conn = get_connection() # connect la db
    cursor = conn.cursor(cursor_factory=RealDictCursor) # execute les requetes sql


    try :

        if request.method == "POST":

            try :
                user_entry = request.form['email_user']
                pwd_entry = request.form['password']

                cursor.execute("SELECT id, nom, prenom, email, mdp, is_admin FROM compte_client WHERE email = %s", (user_entry,))
                user = cursor.fetchone()

                if user and bcrypt.checkpw(pwd_entry.encode('utf-8'), user['mdp'].encode('utf-8')):

                    print('Success')
                    session.permanent = True
                    login_user(User(user))

                    # si l'utilisateur a ete redirige vers /login depuis une page protegee (ex: reservation),
                    # on le renvoie sur cette page apres connexion plutot que sur l'accueil
                    next_page = request.args.get('next')
                    if next_page and next_page.startswith('/'):
                        return redirect(next_page)

                    # un compte administrateur est bascule directement sur le dashboard admin,
                    # separe du site client
                    if user['is_admin']:
                        return redirect(url_for('admin_comptes'))

                    return redirect(url_for('home'))
                else:
                    print("Les identifiants ne correspondent pas ou l'utilisateur n'a pas de compte")

                    return render_template('login.html', login_error=True), 401
            except KeyError:
                return render_template('login.html'),400

        else :
            return render_template('login.html')   
     
    finally:
            cursor.close()
            conn.close()


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route("/mot-de-passe-oublie", methods=['GET', 'POST'])
@limiter.limit('3 per minute', methods=['POST'])
def mot_de_passe_oublie():
    if request.method == 'POST':
        conn = get_connection()
        cursor = conn.cursor()
        try:
            email = (request.form.get('email') or '').strip()

            cursor.execute("SELECT id FROM compte_client WHERE email = %s", (email,))
            user = cursor.fetchone()

            # on genere et envoie un token UNIQUEMENT si le compte existe,
            # mais la reponse HTTP est identique dans tous les cas (anti-enumeration de comptes,
            # meme principe que le message d'erreur generique du login)
            if user:
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
                expires = datetime.datetime.now() + timedelta(minutes=30)

                cursor.execute(
                    "UPDATE compte_client SET reset_token_hash = %s, reset_token_expires = %s WHERE id = %s",
                    (token_hash, expires, user[0])
                )
                conn.commit()

                reset_link = url_for('reinitialiser_mot_de_passe', token=token, _external=True)
                send_reset_email(email, reset_link)

            return render_template('mot_de_passe_oublie.html', success=True)

        finally:
            cursor.close()
            conn.close()

    return render_template('mot_de_passe_oublie.html')


@app.route("/reinitialiser-mot-de-passe/<token>", methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def reinitialiser_mot_de_passe(token):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # le token brut n'est jamais stocke en base : on ne compare que son empreinte,
        # exactement comme pour un mot de passe (si la base fuit, les liens ne sont pas exploitables)
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()

        cursor.execute(
            "SELECT id, reset_token_expires FROM compte_client WHERE reset_token_hash = %s",
            (token_hash,)
        )
        user = cursor.fetchone()

        token_valide = bool(user) and user['reset_token_expires'] is not None and user['reset_token_expires'] > datetime.datetime.now()

        if request.method == 'POST':
            if not token_valide:
                return render_template('reinitialiser_mot_de_passe.html', token_valide=False), 400

            password = request.form.get('password') or ''
            confirm_password = request.form.get('confirm_password') or ''

            if len(password) < 8:
                return render_template('reinitialiser_mot_de_passe.html', token_valide=True, token=token, reset_error=True), 400

            if password != confirm_password:
                return render_template('reinitialiser_mot_de_passe.html', token_valide=True, token=token, reset_error=True), 400

            hash_pwd = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # le token est invalide juste apres usage (usage unique) meme si l'attaquant l'intercepte apres coup
            cursor.execute(
                "UPDATE compte_client SET mdp = %s, reset_token_hash = NULL, reset_token_expires = NULL WHERE id = %s",
                (hash_pwd, user['id'])
            )
            conn.commit()

            return redirect(url_for('login_page', reset='1'))

        return render_template('reinitialiser_mot_de_passe.html', token_valide=token_valide, token=token)

    finally:
        cursor.close()
        conn.close()



@app.route("/reservation/<slug>",methods= ['GET'])
@login_required
def hotel_cibling(slug):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM hotels WHERE slug = %s", (slug,))
    hotel = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('reservation.html', hotel=hotel)


@app.route("/reservation/vols/<int:vol_id>",methods= ['GET'])
@login_required
def vol_cibling(vol_id):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""SELECT vols.id, destinations.ville, destinations.pays, destinations.code_iata,
                          destinations.aeroport, destinations.image,
                          vols.date, vols.heure_depart, vols.prix, vols.compagnie
                   FROM vols
                   JOIN destinations ON vols.destination_id = destinations.id
                   WHERE vols.id = %s""", (vol_id,))



    list_vols = cursor.fetchone()

    cursor.close()
    conn.close()


    return render_template('reservation_vol.html',vol=list_vols)

@app.route("/customers", methods=["POST"]) #pour l'hotel
@login_required
@limiter.limit('10 per minute')
def customers():

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        depart_start = datetime.datetime.strptime(request.form['depart'], "%Y-%m-%d").date()
        depart_end = datetime.datetime.strptime(request.form['sortie'], "%Y-%m-%d").date()
        nuit = (depart_end - depart_start).days

        nombre_adultes = int(request.form['adultes'])
        nombre_enfants = int(request.form['enfants'])

        hotel_slug = request.form['hotel_slug']

        if nombre_adultes < 1 or nombre_enfants < 0:
            return redirect(url_for('hotels'))

        # on ne fait jamais confiance au prix envoyé par le formulaire : on le recalcule depuis la base
        cursor.execute("SELECT id, tarifs FROM hotels WHERE slug = %s", (hotel_slug,))
        hotel = cursor.fetchone()

        if not hotel or nuit <= 0:
            return redirect(url_for('hotels'))

        tarif_total = hotel['tarifs'] * nuit

        cursor.execute("""
            INSERT INTO reservations_hotel
                (client_id, hotel_id, date_arrivee, date_depart, nombre_nuits,
                 nombre_adultes, nombre_enfants, tarif_total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (current_user.id, hotel['id'], depart_start, depart_end, nuit,
              nombre_adultes, nombre_enfants, tarif_total))

        conn.commit()

        return redirect(url_for('panier'))

    except (KeyError, ValueError):
        conn.rollback()
        return redirect(url_for('hotels'))

    finally:
        cursor.close()
        conn.close()


@app.route("/customers/vol", methods=["POST"]) #pour les vols
@login_required
@limiter.limit('10 per minute')
def customers_vols():

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        nombre_adultes = int(request.form['adultes'])
        nombre_enfants = int(request.form['enfants'])

        vol_id = int(request.form['vol_id'])

        if nombre_adultes < 1 or nombre_enfants < 0:
            return redirect(url_for('vols'))

        # on ne fait jamais confiance au prix envoyé par le formulaire : on le recalcule depuis la base
        cursor.execute("SELECT id, prix FROM vols WHERE id = %s", (vol_id,))
        vol = cursor.fetchone()

        if not vol:
            return redirect(url_for('vols'))

        total_personnes = nombre_adultes + nombre_enfants
        prix_total = vol['prix'] * total_personnes

        cursor.execute("""
            INSERT INTO reservations_vol
                (client_id, vol_id, nombre_adultes, nombre_enfants, tarif_total)
            VALUES (%s, %s, %s, %s, %s)
        """, (current_user.id, vol['id'], nombre_adultes, nombre_enfants, prix_total))

        conn.commit()

        return redirect(url_for('panier'))

    except (KeyError, ValueError):
        conn.rollback()
        return redirect(url_for('vols'))

    finally:
        cursor.close()
        conn.close()


@app.route("/panier", methods=['GET'])
@login_required
def panier():

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            SELECT reservations_hotel.id, reservations_hotel.date_arrivee, reservations_hotel.date_depart,
                   reservations_hotel.nombre_nuits, reservations_hotel.nombre_adultes, reservations_hotel.nombre_enfants,
                   reservations_hotel.tarif_total,
                   hotels.nom AS hotel_nom, hotels.adresse AS hotel_adresse, hotels.avis AS hotel_avis,
                   hotels.tarifs AS tarif_nuit
            FROM reservations_hotel
            JOIN hotels ON reservations_hotel.hotel_id = hotels.id
            WHERE reservations_hotel.client_id = %s AND reservations_hotel.statut = 'Non payé'
        """, (current_user.id,))
        liste_H = cursor.fetchall()

        cursor.execute("""
            SELECT reservations_vol.id, reservations_vol.nombre_adultes, reservations_vol.nombre_enfants,
                   reservations_vol.tarif_total,
                   vols.date, vols.heure_depart, vols.prix AS prix_vol,
                   destinations.ville, destinations.pays, destinations.code_iata, destinations.aeroport
            FROM reservations_vol
            JOIN vols ON reservations_vol.vol_id = vols.id
            JOIN destinations ON vols.destination_id = destinations.id
            WHERE reservations_vol.client_id = %s AND reservations_vol.statut = 'Non payé'
        """, (current_user.id,))
        liste_V = cursor.fetchall()

        return render_template('panier.html', reserve=liste_H, vols=liste_V)

    finally:
        cursor.close()
        conn.close()


@app.route('/delete_H/<int:id_reservation_H>', methods=['POST'])
@login_required
@limiter.limit('20 per minute')
def delete_H(id_reservation_H):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # on vérifie que la réservation appartient bien à l'utilisateur connecté (protection IDOR)
        cursor.execute(
            "DELETE FROM reservations_hotel WHERE id = %s AND client_id = %s",
            (id_reservation_H, current_user.id)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('panier'))


@app.route('/delete_V/<int:id_reservation_V>', methods=['POST'])
@login_required
@limiter.limit('20 per minute')
def delete_V(id_reservation_V):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM reservations_vol WHERE id = %s AND client_id = %s",
            (id_reservation_V, current_user.id)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('panier'))


@app.route("/paiements_process", methods=['GET', 'POST'])
@login_required
@limiter.limit('5 per minute', methods=['POST'])
def paiement():

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            "SELECT id FROM reservations_hotel WHERE client_id = %s AND statut = 'Non payé'",
            (current_user.id,)
        )
        reservation_h = cursor.fetchone()

        cursor.execute(
            "SELECT id FROM reservations_vol WHERE client_id = %s AND statut = 'Non payé'",
            (current_user.id,)
        )
        reservation_v = cursor.fetchone()

        if request.method == "POST":
            try:
                name = request.form['nom']
                prenom = request.form['prenom']
                adresse = request.form['adresse']
                ville = request.form['ville']
                code_postal = request.form['cp']
                tel = request.form['tel']
                mail = request.form['mail']
            except KeyError:
                return render_template(
                    'paiement.html',
                    default_nom=current_user.nom,
                    default_prenom=current_user.prenom,
                    default_email=current_user.email,
                ), 400

            if not reservation_h and not reservation_v:
                return redirect(url_for('panier'))

            # on marque toutes les réservations en attente de ce client comme payées
            # et on renseigne les coordonnées du client saisies au moment du paiement
            cursor.execute("""
                UPDATE reservations_hotel
                SET statut = 'Payé', date_paiement = NOW(),
                    nom = %s, prenom = %s, adresse = %s, ville = %s, cp = %s, telephone = %s, email = %s
                WHERE client_id = %s AND statut = 'Non payé'
            """, (name, prenom, adresse, ville, code_postal, tel, mail, current_user.id))

            cursor.execute("""
                UPDATE reservations_vol
                SET statut = 'Payé', date_paiement = NOW(),
                    nom = %s, prenom = %s, adresse = %s, ville = %s, cp = %s, telephone = %s, email = %s
                WHERE client_id = %s AND statut = 'Non payé'
            """, (name, prenom, adresse, ville, code_postal, tel, mail, current_user.id))

            cursor.execute(
                "INSERT INTO paiements (nom_prenom) VALUES (%s)",
                (f"{name} {prenom}",)
            )

            conn.commit()

            return redirect(url_for('success', type='reservation'))

        else:
            if not reservation_h and not reservation_v:
                return redirect(url_for('panier'))

            return render_template(
                'paiement.html',
                default_nom=current_user.nom,
                default_prenom=current_user.prenom,
                default_email=current_user.email,
            )

    finally:
        cursor.close()
        conn.close()


@app.route('/destinations', methods=['GET'])
@login_required
def mes_destinations():

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            SELECT reservations_hotel.date_arrivee, reservations_hotel.date_depart,
                   reservations_hotel.nombre_nuits, reservations_hotel.nombre_adultes, reservations_hotel.nombre_enfants,
                   reservations_hotel.tarif_total, reservations_hotel.nom, reservations_hotel.prenom,
                   reservations_hotel.date_paiement,
                   hotels.nom AS hotel_nom, hotels.adresse AS hotel_adresse, hotels.ville AS hotel_ville,
                   hotels.tarifs AS tarif_nuit
            FROM reservations_hotel
            JOIN hotels ON reservations_hotel.hotel_id = hotels.id
            WHERE reservations_hotel.client_id = %s AND reservations_hotel.statut = 'Payé'
            ORDER BY reservations_hotel.date_paiement DESC
        """, (current_user.id,))
        destinations_h = cursor.fetchall()

        cursor.execute("""
            SELECT reservations_vol.nombre_adultes, reservations_vol.nombre_enfants,
                   reservations_vol.tarif_total, reservations_vol.nom, reservations_vol.prenom,
                   reservations_vol.date_paiement,
                   vols.date, vols.heure_depart, vols.prix AS prix_vol,
                   destinations.ville, destinations.pays, destinations.code_iata, destinations.aeroport
            FROM reservations_vol
            JOIN vols ON reservations_vol.vol_id = vols.id
            JOIN destinations ON vols.destination_id = destinations.id
            WHERE reservations_vol.client_id = %s AND reservations_vol.statut = 'Payé'
            ORDER BY reservations_vol.date_paiement DESC
        """, (current_user.id,))
        destinations_v = cursor.fetchall()

        return render_template('mes_destinations.html', reserve_hotels=destinations_h, reserve_vols=destinations_v)

    finally:
        cursor.close()
        conn.close()


@app.route("/profil", methods=['GET'])
@login_required
def profil():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id, nom, prenom, email FROM compte_client WHERE id = %s", (current_user.id,))
        user = cursor.fetchone()
        return render_template('profil.html', user=user)
    finally:
        cursor.close()
        conn.close()


@app.route("/profil", methods=['PUT'])
@login_required
@limiter.limit('10 per minute')
def profil_update():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json(silent=True) or request.form

        nom = (data.get('nom') or '').strip()
        prenom = (data.get('prenom') or '').strip()
        email = (data.get('email') or '').strip()

        if not nom or not prenom or not email:
            return jsonify({"error": "Tous les champs sont obligatoires."}), 400

        cursor.execute(
            "UPDATE compte_client SET nom = %s, prenom = %s, email = %s WHERE id = %s",
            (nom, prenom, email, current_user.id)
        )
        conn.commit()
        return jsonify({"success": True, "nom": nom, "prenom": prenom, "email": email}), 200

    except errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "Cette adresse mail est déjà utilisée par un autre compte."}), 409

    finally:
        cursor.close()
        conn.close()


@app.route("/profil/password", methods=['PATCH'])
@login_required
@limiter.limit('5 per minute')
def profil_update_password():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json(silent=True) or request.form

        current_pwd = data.get('current_password') or ''
        new_pwd = data.get('new_password') or ''
        confirm_pwd = data.get('confirm_new_password') or ''

        cursor.execute("SELECT mdp FROM compte_client WHERE id = %s", (current_user.id,))
        row = cursor.fetchone()

        if not row or not bcrypt.checkpw(current_pwd.encode('utf-8'), row[0].encode('utf-8')):
            return jsonify({"error": "Mot de passe actuel incorrect."}), 401

        if len(new_pwd) < 8:
            return jsonify({"error": "Le nouveau mot de passe doit contenir au moins 8 caractères."}), 400

        if new_pwd != confirm_pwd:
            return jsonify({"error": "Les nouveaux mots de passe ne correspondent pas."}), 400

        hash_pwd = bcrypt.hashpw(new_pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("UPDATE compte_client SET mdp = %s WHERE id = %s", (hash_pwd, current_user.id))
        conn.commit()
        return jsonify({"success": True}), 200

    finally:
        cursor.close()
        conn.close()


@app.route("/profil", methods=['DELETE'])
@login_required
@limiter.limit('3 per minute')
def profil_delete():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json(silent=True) or request.form
        pwd_confirm = data.get('password') or ''

        cursor.execute("SELECT mdp FROM compte_client WHERE id = %s", (current_user.id,))
        row = cursor.fetchone()

        if not row or not bcrypt.checkpw(pwd_confirm.encode('utf-8'), row[0].encode('utf-8')):
            return jsonify({"error": "Mot de passe incorrect."}), 401

        # on supprime d'abord les reservations liees (pas de ON DELETE CASCADE en base)
        # avant de supprimer le compte, sinon la contrainte FOREIGN KEY bloque le DELETE
        cursor.execute("DELETE FROM reservations_hotel WHERE client_id = %s", (current_user.id,))
        cursor.execute("DELETE FROM reservations_vol WHERE client_id = %s", (current_user.id,))
        cursor.execute("DELETE FROM compte_client WHERE id = %s", (current_user.id,))
        conn.commit()

        logout_user()
        return jsonify({"success": True}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Erreur lors de la suppression du compte."}), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/mentions-legales", methods=['GET'])
def mentions_legales():
    return render_template('mentions_legales.html')


@app.route("/confidentialite", methods=['GET'])
def confidentialite():
    return render_template('confidentialite.html')


@app.route("/cgv", methods=['GET'])
def cgv():
    return render_template('cgv.html')


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")#attention a ne pas mettre en true en prod !!!!!!! 
    