import mysql.connector
from mysql.connector import errorcode
from base import *
from base.constants import *

conn = None
all_good = None

# only kodi_mysql_init_and_verify has smart try-except fallbacks as other calls must 100% work if database is not messed up during process

def kodi_mysql_init_and_verify():
    global conn
    global all_good

    # do not retry if already done
    if all_good == True:
        logger.debug(". kodi mysql allgood already tried")
        return True

    try:
        # Establish a connection to the MySQL server (** is unpacking the dict into keyed args)
        conn = mysql.connector.connect(**KODI_MYSQL_CONFIG)
        cursor = conn.cursor()

        # Query to check if the database exists
        cursor.execute("SHOW DATABASES LIKE 'kodi_video131';")
        result = cursor.fetchone()

        if result:
            logger.info("> Kodi local MYSQL database has been instanciated and is connected")
            all_good = True # faster later and no useless reconnection
            return True
        else:
            logger.critical("!!! Database 'kodi_video131' db must have been deleted during the process, please run kodi to reinstanciate it (guide: https://github.com/philamp/jellygrail/wiki/Configure-Kodi), no need to restart Jellygrail")
            all_good = False
            mariadb_close()
            return False

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.critical("!!! Something is wrong with the kodi mysql username or password, theorically impossible unless you messed up inside mysql server. Rebuild the docker image to fix it :( ")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logger.warning("! Kodi Mysql Database does not exist, please instanciate it (guide: https://github.com/philamp/jellygrail/wiki/Configure-Kodi) for all processes involving Kodi to work, no need to restart Jellygrail")
        else:
            logger.critical(err)
        return False

def check_if_vvtype_exists(test_string):
    global conn
    # Création d'un curseur pour exécuter des requêtes SQL
    cursor = conn.cursor(buffered=True)

    # Exécution d'une requête
    cursor.execute(f"SELECT id FROM videoversiontype where name = %s", (test_string,))

    result = cursor.fetchone()

    logger.debug("--- vv merging passing through ----")
    cursor.close() 

    if result:
        return result[0]
    
    return 0


def delete_other_mediaid(imediatodel):
    global conn
    cursor = conn.cursor()

    # Exécution d'une requête
    cursor.execute(f"DELETE FROM movie where idMovie = %s", (imediatodel,))

    conn.commit()

    cursor.close() 
    # Récupération des résultats
    return True

def define_kept_mediaid(idfile, strpath, imediatokeep):
    global conn
    cursor = conn.cursor()

    # Exécution d'une requête
    cursor.execute(f"UPDATE movie set idFile = %s, c22 = %s where idMovie = %s", (idfile,strpath,imediatokeep))

    conn.commit()

    cursor.close() 
    # Récupération des résultats
    return True

def insert_new_vvtype(new_string):

    global conn
    cursor = conn.cursor()

    # Exécution d'une requête
    cursor.execute(f"insert into videoversiontype (name, owner, itemType) values (%s, 0,0)", (new_string,))

    conn.commit()

    inserted_id = cursor.lastrowid

    cursor.close() 

    return inserted_id



def link_vv_to_kept_mediaid(vvid, keptmid, new_type_id):
    global conn
    cursor = conn.cursor()

    cursor.execute(f"UPDATE videoversion set idMedia = %s, idType = %s where idFile = %s", (keptmid,new_type_id,vvid))

    conn.commit()

    cursor.close() 
    # Récupération des résultats
    return True

def video_versions():
    global conn
    # Création d'un curseur pour exécuter des requêtes SQL
    cursor = conn.cursor(buffered=True)

    # Exécution d'une requête
    cursor.execute(f"SELECT uid.value as tmdbid, group_concat(mvb.idMovie SEPARATOR ' ') as idmedia, group_concat(mvb.strPath SEPARATOR ' ') as strpath, group_concat(mvb.strFileName SEPARATOR ' ') as strfilename, group_concat(mvb.videoVersionIdFile SEPARATOR ' ') as idfile, group_concat(isDefaultVersion SEPARATOR ' ') as isdefault FROM movie_view mvb left join uniqueid uid on uid.media_id = mvb.idMovie where uid.type = 'tmdb' GROUP BY uid.value HAVING COUNT(*) > 1")

    result = cursor.fetchall()
    cursor.close() 
    # Récupération des résultats
    return result

def fetch_media_id(path, tabletofetch, idtofetch):
    global conn
    # Création d'un curseur pour exécuter des requêtes SQL
    cursor = conn.cursor()

    like_param = f"%{path}%"

    # Exécution d'une requête
    cursor.execute(f"SELECT ttf.{idtofetch}, MIN(uid.type) as type FROM {tabletofetch} ttf LEFT JOIN uniqueid uid on uid.media_id = ttf.{idtofetch} WHERE strPath like %s GROUP BY ttf.{idtofetch}", (like_param,))

    result = cursor.fetchall(buffered=True)
    cursor.close() 
    # Récupération des résultats
    return result

def mariadb_close():
    global conn
    conn.close()
