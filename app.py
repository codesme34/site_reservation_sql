from flask import Flask, request, jsonify,render_template,redirect,url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from psycopg2 import errors
from Database.db import get_connection
from flask_login import LoginManager,UserMixin,logout_user,login_user,login_required,current_user

import bcrypt
import os

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

            hash_pwd = bcrypt.hashpw(pwd_user.encode('utf-8'), bcrypt.gensalt())

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


                if user and bcrypt.checkpw(pwd_entry.encode('utf-8'), bytes(user[4])):
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


@app.route("/")
def home():
    return render_template('index.html')

    

if __name__ == "__main__":
    app.run(debug=True)#attention a ne pas mettre en true en prod !!!!!!! 
    