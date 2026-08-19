from flask import Flask, request, jsonify,render_template,redirect,url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from psycopg2 import errors
from Database.db import get_connection
from flask_login import LoginManager,UserMixin,logout_user,login_user,login_required,current_user
import bcrypt
import os
from psycopg2.extras import RealDictCursor
import random



app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
limiter = Limiter(app=app, key_func=get_remote_address)

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
        SELECT destinations.ville, destinations.pays, destinations.code_iata,
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
def search():

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        type_recherche = request.form['type']

        if type_recherche == 'hotel':
            destination = request.form['destination_h']
            cursor.execute("SELECT * FROM hotels WHERE ville = %s", (destination))
            resultats = cursor.fetchall()

        else:
            destination = request.form['destination_v']
            cursor.execute("""
                SELECT destinations.*, vols.date, vols.heure_depart, vols.prix, vols.compagnie
                FROM vols
                JOIN destinations ON vols.destination_id = destinations.id
                WHERE destinations.pays = %s
            """, (destination,))
            resultats = cursor.fetchall()

        return render_template('recherche.html', resultats=resultats, type=type_recherche)

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
@limiter.limit('1 per minute', methods=['POST'])
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

            return redirect(url_for('success'))

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
    return render_template('thankyou.html')
    


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
            return jsonify({"error": "Champ manquant dans la requête"}), 400

        except errors.UniqueViolation:
            conn.rollback()
            return jsonify({"error": "Cet email est déjà utilisé"}), 409


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
                    login_user(User(user))
                    
                    # 4. On renvoie l'objet réponse complet
                    return redirect(url_for('home'))
                else:
                    print("Les identifiants ne correspondent pas ou l'utilisateur n'a pas de compte")
                    
                    return render_template('login.html') 
            except KeyError:
                return render_template('login.html'),400

        else :
            return render_template('login.html')   
     
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


    

if __name__ == "__main__":
    app.run(debug=True)#attention a ne pas mettre en true en prod !!!!!!! 
    