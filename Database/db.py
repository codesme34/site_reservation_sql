import os
import psycopg2
from dotenv import load_dotenv


load_dotenv()

def get_connection():

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))

    return conn

if __name__ == "__main__":
    conn = get_connection()
    print("Connexion réussie :", conn)
    conn.close()
