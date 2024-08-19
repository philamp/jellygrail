import mysql.connector

# Connexion à la base de données
conn = mysql.connector.connect(
    host="localhost",
    user="kodi",
    password="kodi",
    database="kodi_video131",
    port=6503
)

def fetch_media_id(path, tabletofetch, idtofetch):
    # Création d'un curseur pour exécuter des requêtes SQL
    cursor = conn.cursor()

    like_param = f"%{path}%"

    # Exécution d'une requête
    cursor.execute(f"SELECT {idtofetch} FROM {tabletofetch} WHERE strPath like %s", (like_param,))

    result = cursor.fetchall()
    cursor.close() 
    # Récupération des résultats
    return result

def mariadb_close():
    # Fermeture du curseur et de la connexion
    #todo  put on shutdown
    conn.close()