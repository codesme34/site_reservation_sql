from pymongo import MongoClient
from Database.db import get_connection

mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["Site_reservation"]
vols_mongo = mongo_db["Vols_europe"]

conn = get_connection()
cursor = conn.cursor()

for doc in vols_mongo.find():

    # 1. insérer la destination et récupérer son id généré
    cursor.execute(
        """INSERT INTO destinations (ville, pays, code_iata, aeroport, image)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING id""",
        (doc["ville"], doc["pays"], doc["code_iata"], doc["aeroport"], doc["image"])
    )
    destination_id = cursor.fetchone()[0]

    # 2. insérer chaque vol du tableau, lié à cette destination
    for vol in doc["vols"]:
        cursor.execute(
            """INSERT INTO vols (destination_id, date, heure_depart, prix, compagnie)
               VALUES (%s, %s, %s, %s, %s)""",
            (destination_id, vol["date"], vol["heure_depart"], vol["prix"], vol["compagnie"])
        )

conn.commit()
cursor.close()
conn.close()

print("Migration des vols terminée")
