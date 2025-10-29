from base import *
from base.constants import *

import asyncio
import socket


# ----

import shlex
import struct
import os

from jgscan import get_fastpass_ffprobe
from nfo_generator import fetch_nfo

async def SSDPTask(ctx, stop):
    # ctx not used, would be elegant to put sock in ctx and to use existing timeout handling in jobmanager
    
    # testablée with nc -ul 
    pause = 5

    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    #sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)  # <-- important

    #       0    1         2        3                          4                                  5                      6
    msg = f"JGx|{VERSION}|{LAN_IP}|{WEBSERVICE_INTERNAL_PORT}|{KODI_MYSQL_CONFIG.get('port', 0)}|{WEBDAV_INTERNAL_PORT}|{SSDP_TOKEN}"

    logger.info(f"      SSDP| Broadcasting this SSDP msg: {msg} ")
    try:
        while not stop.is_set():
            await loop.sock_sendto(sock, msg.encode("ascii"), ("239.255.255.250", SSDP_PORT))
            try:
                await asyncio.wait_for(stop.wait(), timeout=pause)
            except asyncio.TimeoutError:
                pass
    finally:
        sock.close()
        logger.info("      SSDP| Broadcast socket closed.")

async def handle_ffprobe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    while True:
        data = await reader.read(1024)
        if not data:
            break

        args = shlex.split(data.decode('utf-8'))
        rkey = 3
        for key, arg in enumerate(args):
            if arg == "-i":
                rkey = key + 1

        messagein = args[rkey]
        stdout, stderr, returncode = await asyncio.to_thread(get_fastpass_ffprobe, messagein)

        messageout = (
            struct.pack('!I', len(stdout)) + stdout +
            struct.pack('!I', len(stderr)) + stderr +
            struct.pack('!i', returncode)
        )
        writer.write(messageout)
        await writer.drain()

    writer.close()
    await writer.wait_closed()
    logger.debug("ffprobe socket closed.")


async def handle_nfopath(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    logger.info(f"     SOCKET/ ...BindFS connected")
    while True:
        data = await reader.read(1024)
        if not data:
            logger.error("    SOCKET/ nfopath socket disconnected (BindFS instance must have crashed!!)")
            break

        message = data.decode('utf-8')
        response = await asyncio.to_thread(fetch_nfo, message)
        writer.write(response.encode('utf-8'))
        await writer.drain()

    writer.close()
    await writer.wait_closed()
    logger.debug("nfopath socket closed.")

async def socket_server_waiting(socket_type: str):
    server_address = f'/tmp/jelly_{socket_type}_socket'

    # Ensure old socket is removed
    try:
        os.unlink(server_address)
    except FileNotFoundError:
        pass

    handler = handle_ffprobe if socket_type == "ffprobe" else handle_nfopath

    server = await asyncio.start_unix_server(handler, path=server_address)
    os.chmod(server_address, 0o777)

    if socket_type == "ffprobe":
        logger.info(f"    SOCKET/ Waiting for any {socket_type} wrapper transaction ~")
    else:
        logger.info(f"    SOCKET/ BindFS waiting connection...")

    async with server:
        await server.serve_forever()

def start_uvloop_thread():
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run_uvloop_servers():
        await asyncio.gather(
            socket_server_waiting("ffprobe"),
            socket_server_waiting("nfopath")
        )

    loop.run_until_complete(run_uvloop_servers())