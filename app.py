from flask import Flask, request, render_template,redirect,url_for
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

# admin avec delete , put , insert, delete hotel avec et sans frameworks,
# ameliorer le formulaire 
# la rgpd
# pop up js 
# utilise du js obligatoire 
# inclusitvite,navigation clavier
# parler des alt pour le front
# penser au gens qui sont dixelitique, non voyant etc ...
# utiliser du js pour du carousel par exemple....
# mettre du bouton 
# contacte rate limit pas de pop up qui affiche un message vous avez trop essayer etc...
#proteger du spam


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
    def __init__(self, user_row):
        self.id = str(user_row[0])#je le met sous forme de cle car avec sql c'est du tuple et pas un dic comme mongodb
        self.nom = user_row[1]
        self.prenom = user_row[2]
        self.email = user_row[3]

        

@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nom, prenom, email FROM compte_client WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user)
    return None


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
@limiter.limit('1 per minute',methods=['POST'])
def creation_compte():

    conn = get_connection() # connect la db 
    cursor = conn.cursor() # execute les requetes sql

    if request.method == 'POST':
        

        try : 

            nom_user = request.form['nom']
            prenom_user = request.form['prenom']
            mail_user = request.form['email']
            pwd_user = request.form['password']

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
            return render_template('creation_compte.html', email_exists=True), 409


        finally:
            cursor.close()
            conn.close()
        
    else:
        return render_template('creation_compte.html')

    

@app.route("/login", methods=["GET", "POST"])
@limiter.limit('5 per minute', methods=['POST'])
def login_page():

    conn = get_connection() # connect la db 
    cursor = conn.cursor() # execute les requetes sql


    try :

        if request.method == "POST":

            try : 
                user_entry = request.form['email_user']
                pwd_entry = request.form['password']

                cursor.execute("SELECT id, nom, prenom, email, mdp FROM compte_client WHERE email = %s", (user_entry,))
                user = cursor.fetchone()

                if user and bcrypt.checkpw(pwd_entry.encode('utf-8'), user[4].encode('utf-8')):

                    print('Success')
                    session.permanent = True
                    login_user(User(user))

                    # si l'utilisateur a ete redirige vers /login depuis une page protegee (ex: reservation),
                    # on le renvoie sur cette page apres connexion plutot que sur l'accueil
                    next_page = request.args.get('next')
                    if next_page and next_page.startswith('/'):
                        return redirect(next_page)

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
                return render_template('paiement.html'), 400

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

            return render_template('paiement.html')

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
    

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")#attention a ne pas mettre en true en prod !!!!!!! 
    