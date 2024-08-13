import mysql.connector

# Connexion à la base de données
conn = mysql.connector.connect(
    host="localhost",
    user="kodi",
    password="kodi",
    database="kodi_video131",
    port=6503
)

def test():
    # Création d'un curseur pour exécuter des requêtes SQL
    cursor = conn.cursor()

    # Exécution d'une requête
    cursor.execute("SELECT * FROM movie")

    # Récupération des résultats
    resultats = cursor.fetchall()

    for ligne in resultats:
        print(ligne[2])

    # Fermeture du curseur et de la connexion
    cursor.close()
    conn.close()