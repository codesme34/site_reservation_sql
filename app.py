from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from psycopg2 import errors
from Database.db import get_connection
import bcrypt
import os

app = Flask(__name__)

limiter = Limiter(app=app, key_func=get_remote_address)

@app.route("/compte_client",methods=['POST'])
@limiter.limit('1 per minute')
def creation_compte():

    conn = get_connection() # connect la db 
    cursor = conn.cursor() # execute les requetes sql

    data = request.get_json()
    try : 

        nom_client = data['nom']
        prenom_client = data['prenom']

        email = data['email']

        mdp = data['mot_de_passe']

        mdp_hash = bcrypt.hashpw(mdp.encode('utf-8'), bcrypt.gensalt())

        # attention a bien mettre le parametre '%s' pour eviter les attaques jamais mettre de f'string (f'insert to .....')
        cursor.execute(
        "INSERT INTO compte_client (nom, prenom, email, mdp) VALUES (%s, %s, %s, %s)",
        (nom_client, prenom_client, email, mdp_hash))

        conn.commit()

        return jsonify({"message": "Compte créé avec succès"}), 201  #le code 201 est une bonne pratique REST

    except KeyError:
        conn.rollback() # lr rollback annule la transaction en cours en cas d'erreur — sans ça, la connexion reste dans un état "planté" et la prochaine requête sur cette connexion échouerait aussi.
        return jsonify({"error": "Champ manquant dans la requête"}), 400

    except errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "Cet email est déjà utilisé"}), 409


    finally:
        cursor.close()
        conn.close()
    


if __name__ == "__main__":
    app.run(debug=True)
    