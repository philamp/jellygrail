import socket
import time
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("8.8.8.8", 80))  # Google DNS, juste pour forcer la sortie par le LAN
    local_ip = s.getsockname()[0]
except Exception as e:
    print(f"Error when trying to guess LAN IP: {e}")
else:
    print(local_ip)
finally:
    s.close()



BROADCAST_PORT = 6505 

WSP = "6502"

msg = local_ip + "|" + str(WSP)

encmsg = msg.encode("ascii")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

while False:
    sock.sendto(encmsg, ("<broadcast>", BROADCAST_PORT))
    print(f"Annonce envoyée sur {BROADCAST_PORT}")
    time.sleep(5)

#-----


BROADCAST_PORT = 44555  # le même que côté serveur

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", BROADCAST_PORT))   # écoute sur tout le LAN

sock.settimeout(10)
try:
    data, addr = sock.recvfrom(1024)
    msg = data.decode()
    xbmc.log(f"[MyAddon] Message reçu de {addr}: {msg}", xbmc.LOGINFO)

    parts = msg.split("|")
    if parts[0] == "MYKODISERVER":
        host = addr[0]        # IP du serveur qui a broadcasté
        port = int(parts[1])  # port du service (ex: HTTP 5000)
        xbmc.log(f"[MyAddon] Serveur détecté: {host}:{port}", xbmc.LOGINFO)
except socket.timeout:
    xbmc.log("[MyAddon] Aucun serveur détecté", xbmc.LOGWARNING)