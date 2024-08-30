import mysql.connector

# Connexion à la base de données
conn = mysql.connector.connect(
    host="localhost",
    user="kodi",
    password="kodi",
    database="kodi_video131",
    port=6503
)


def delete_other_mediaid(imediatodel):

    cursor = conn.cursor()

    # Exécution d'une requête
    cursor.execute(f"DELETE FROM movie where idMovie = %s", (imediatodel,))

    conn.commit()

    cursor.close() 
    # Récupération des résultats
    return True

def define_kept_mediaid(idfile, strpath, imediatokeep):

    cursor = conn.cursor()

    # Exécution d'une requête
    cursor.execute(f"UPDATE movie set idFile = %s, c22 = %s where idMovie = %s", (idfile,strpath,imediatokeep))

    conn.commit()

    cursor.close() 
    # Récupération des résultats
    return True

def link_vv_to_kept_mediaid(vvid, keptmid):

    cursor = conn.cursor()

    # Exécution d'une requête
    cursor.execute(f"UPDATE videoversion set idMedia = %s where idFile = %s", (keptmid,vvid))

    conn.commit()

    cursor.close() 
    # Récupération des résultats
    return True

def video_versions():
    # Création d'un curseur pour exécuter des requêtes SQL
    cursor = conn.cursor()

    # Exécution d'une requête
    cursor.execute(f"SELECT uid.value as tmdbid, group_concat(mvb.idMovie SEPARATOR '¨') as idmedia, group_concat(mvb.strPath SEPARATOR '¨') as strpath, group_concat(mvb.strFileName SEPARATOR '¨') as strfilename, group_concat(mvb.videoVersionIdFile SEPARATOR '¨') as idfile, group_concat(isDefaultVersion SEPARATOR '¨') as isdefault FROM movie_view mvb left join uniqueid uid on uid.media_id = mvb.idMovie where uid.type = 'tmdb' GROUP BY uid.value HAVING COUNT(*) > 1")

    result = cursor.fetchall()
    cursor.close() 
    # Récupération des résultats
    return result

def fetch_media_id(path, tabletofetch, idtofetch):
    # Création d'un curseur pour exécuter des requêtes SQL
    cursor = conn.cursor()

    like_param = f"%{path}%"

    # Exécution d'une requête
    cursor.execute(f"SELECT ttf.{idtofetch}, MIN(uid.type) as type FROM {tabletofetch} ttf LEFT JOIN uniqueid uid on uid.media_id = ttf.{idtofetch} WHERE strPath like %s GROUP BY ttf.{idtofetch}", (like_param,))

    result = cursor.fetchall()
    cursor.close() 
    # Récupération des résultats
    return result

def mariadb_close():
    # Fermeture du curseur et de la connexion
    #todo  put on shutdown
    conn.close()