import mysql.connector
from mysql.connector import errorcode
from base import *
from base.constants import *

conn = None

# kodi mysql config
KODI_MYSQL_CONFIG = {
    'host' : 'localhost',
    'user' : 'kodi',
    'password' : 'kodi',
    #'database' : 'kodi_video131',
    'port' : 6503
}

found_db = ""


# only kodi_mysql_init_and_verify has smart try-except fallbacks as other calls must 100% work if database is not messed up during process

def kodi_mysql_init_and_verify(just_verify=False):
    global conn
    global found_db

    try:
        # Establish a connection to the MySQL server (** is unpacking the dict into keyed args)
        conn = mysql.connector.connect(**KODI_MYSQL_CONFIG)
        cursor = conn.cursor(buffered=True)

        # Query to check if the database exists
        cursor.execute("SHOW DATABASES LIKE 'kodi_video%'")
        result = cursor.fetchall()

        results = [res[0] for res in result]

        found_db = results[-1]

        cursor.close() # important
        if result:
            if just_verify:
                logger.info("  SQL-KODI| Working ok")
                mariadb_close()
            else:
                logger.debug(". MySQL Connection ok")
                # we don't close connection
            return True
        else:
            logger.warning("  SQL-KODI| Not working. Please instanciate DB in Kodi (guide: https://github.com/philamp/jellygrail/wiki/Configure-Kodi), no need to restart Jellygrail")
            mariadb_close()
            return False

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.error("  SQL-KODI| Authentication failed. Container mariadb setup failed on your system. Please report in the github.")
        else:
            logger.critical(f"  SQL-KODI| SQL server messed-up. Container mariadb setup failed on your system. Please report in the github. Error is: {err}")
        return False

def check_if_vvtype_exists(test_string):
    global conn
    # Création d'un curseur pour exécuter des requêtes SQL
    cursor = conn.cursor(buffered=True)

    # Exécution d'une requête
    cursor.execute(f"USE {found_db}")
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
    cursor.execute(f"USE {found_db}")
    cursor.execute(f"DELETE FROM movie where idMovie = %s", (imediatodel,))

    conn.commit()

    cursor.close() 
    # Récupération des résultats
    return True

def define_kept_mediaid(idfile, strpath, imediatokeep):
    global conn
    cursor = conn.cursor()

    # Exécution d'une requête
    cursor.execute(f"USE {found_db}")
    cursor.execute(f"UPDATE movie set idFile = %s, c22 = %s where idMovie = %s", (idfile,strpath,imediatokeep))

    conn.commit()

    cursor.close() 
    # Récupération des résultats
    return True

def insert_new_vvtype(new_string):

    global conn
    cursor = conn.cursor()

    # Exécution d'une requête
    cursor.execute(f"USE {found_db}")
    cursor.execute(f"insert into videoversiontype (name, owner, itemType) values (%s, 0,0)", (new_string,))

    conn.commit()

    inserted_id = cursor.lastrowid

    cursor.close() 

    return inserted_id



def set_resume_times_and_lastplayed(timesec, lastplayedstr, fileidsstr, idfiles, highest_tt):
    #todo update or insert !!
    global conn
    cursor = conn.cursor()

    cursor.execute(f"USE {found_db}")

    if timesec:

        for fileid in idfiles:
            
            cursor.execute(f"SELECT idFile FROM bookmark where idFile = %s", (fileid,))
            result = cursor.fetchone()

            if result:
                cursor.execute(f"UPDATE bookmark set timeInSeconds = %s WHERE idFile = %s", (timesec,fileid))
            else:
                cursor.execute(f"INSERT INTO bookmark (idFile, timeInSeconds, totalTimeInSeconds, player, type) VALUES (%s, %s, %s, 'VideoPlayer', 1) ON DUPLICATE KEY UPDATE timeInSeconds = VALUES(timeInSeconds)", (fileid,timesec,highest_tt))


        #cursor.execute(f"UPDATE bookmark set timeInSeconds = %s WHERE idFile in ({fileidsstr})", (timesec,))
    if lastplayedstr:
        cursor.execute(f"UPDATE files set lastPlayed = %s WHERE idFile in ({fileidsstr})", (lastplayedstr,))

    conn.commit()

    cursor.close() 

    return True



def link_vv_to_kept_mediaid(vvid, keptmid, new_type_id):
    global conn
    cursor = conn.cursor()
    cursor.execute(f"USE {found_db}")

    cursor.execute(f"UPDATE videoversion set idMedia = %s, idType = %s where idFile = %s", (keptmid,new_type_id,vvid))

    conn.commit()

    cursor.close() 

    return True

def video_versions():
    global conn
    # Création d'un curseur pour exécuter des requêtes SQL
    cursor = conn.cursor(buffered=True)
    cursor.execute(f"USE {found_db}")

    # Exécution d'une requête
    cursor.execute(f"SELECT uid.value as tmdbid, group_concat(mvb.idMovie SEPARATOR ' ') as idmedia, group_concat(mvb.strPath SEPARATOR ' ') as strpath, group_concat(mvb.strFileName SEPARATOR ' ') as strfilename, group_concat(mvb.videoVersionIdFile SEPARATOR ',') as idfile, group_concat(isDefaultVersion SEPARATOR ' ') as isdefault, group_concat(lastPlayed SEPARATOR '#') as lastPlayed, group_concat(resumeTimeInSeconds SEPARATOR ' ') as resumeTimeInSeconds, group_concat(mvb.totalTimeInSeconds SEPARATOR ' ') as totalTimeInSeconds FROM movie_view mvb left join uniqueid uid on uid.media_id = mvb.idMovie where uid.type = 'tmdb' GROUP BY uid.value HAVING COUNT(*) > 1")

    result = cursor.fetchall()
    cursor.close() 
    # Récupération des résultats
    return result

def fetch_media_id(path, tabletofetch, idtofetch):
    global conn
    # Création d'un curseur pour exécuter des requêtes SQL
    cursor = conn.cursor(buffered=True)
    cursor.execute(f"USE {found_db}")

    like_param = f"%{path}%"

    # Exécution d'une requête
    cursor.execute(f"SELECT ttf.{idtofetch}, MIN(uid.type) as type FROM {tabletofetch} ttf LEFT JOIN uniqueid uid on uid.media_id = ttf.{idtofetch} WHERE strPath like %s GROUP BY ttf.{idtofetch}", (like_param,))

    result = cursor.fetchall()
    cursor.close() 
    # Récupération des résultats
    return result

def get_undefined_collection_arts():
    global conn
    cursor = conn.cursor()
    cursor.execute(f"USE {found_db}")
    cursor.execute("SELECT * FROM sets s WHERE NOT EXISTS (SELECT 1 FROM art a WHERE a.media_type = 'set' AND a.media_id = s.idSet)")
    return cursor.fetchall()


def insert_collection_art(id, strpath):
    global conn
    cursor = conn.cursor()
    cursor.execute(f"USE {found_db}")

    # Exécution d'une requête
    cursor.execute("INSERT INTO art (media_id, media_type, type, url) VALUES (%s, 'set', 'thumb', %s)", (id, strpath))

    conn.commit()

    cursor.close() 

    return True

def mariadb_close():
    global conn
    conn.close()
