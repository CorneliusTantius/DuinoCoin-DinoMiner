from datetime import datetime
from hashlib import sha1
from socket import socket
from time import time, sleep
from random import randint
import requests
import multiprocessing

VER = '1.2'
WORKER = f'ID{randint(1001, 9998)}'
USERNAME = 'corneliustantius'
DIFFICULTY = 'MEDIUM'
PORT_URL = 'https://server.duinocoin.com/getPool'
DEFAULT_NODE = ('server.duinocoin.com', 2813)

THREADS_COUNT = 2


def logger(type:int, message:str, thread_num = 0):
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[31m'
    YELLOW = '\033[93m'
    CYAN = "\033[36m"
    ENDC = '\033[0m'
    
    log = "INFO" if type == 1 else "WARN" if type == 2 else "MINER"
    colorama = BLUE if type == 1 else YELLOW if type == 2 else CYAN
    if type == 0:
        print(f'[T{thread_num}]{colorama}[{log}]{ENDC} {GREEN}[GOOD]{ENDC} {message}')
    elif type == 9:
        print(f'[T{thread_num}]{colorama}[{log}]{ENDC} {RED}[BAD]{ENDC} {message}')
    else:
        print(f'[T{thread_num}]{colorama}[{log}]{ENDC} {message}')

def fetch_node(thread_num):
    logger(1, "Fetching node details", thread_num)
    fails = 0
    while 1:
        try:
            response = requests.get(PORT_URL).json()
            active = response["connections"]
            name = response["name"]
            logger(1, f"{name} address obtained, {active} active connections", thread_num)
            print(), logger(1, f"Connecting to {name} . . .", thread_num)
            return (str(response["ip"]), int(response["port"]))
        except Exception as e:
            fails += 1
            if fails >= 5:
                logger(2, "Failed too much while fetching Node", thread_num)
                logger(1, "Using default Node details", thread_num)
                return DEFAULT_NODE
            logger(2, "Failed to fetch node details, "+str(e), thread_num)
            logger(1, "Retrying in 15 seconds", thread_num)
            sleep(15) 

def fetch_socket(NODE_DETAIL, thread_num):
    soc, fails = None, 0
    while 1:
        try:
            if socket():
                socket().close()
            if fails >= 3:
                logger(1, "Failed too much, re-fetching node details", thread_num)
                NODE_DETAIL = fetch_node()
                fails = 0
            soc = socket()
            soc.settimeout(60)
            soc.connect(NODE_DETAIL)
            
            server_version = soc.recv(100).decode()
            soc.send(bytes("MOTD", encoding="utf8"))
            motd = soc.recv(100).decode().split("\n")
            logger(1, f"Active server version: {server_version}", thread_num)
            logger(1, motd[0], thread_num), logger(1, motd[1], thread_num), print()
            return soc
        except Exception as e:
            fails += 1
            logger(2, "Failed connecting to socket, "+str(e), thread_num)
            logger(1, "Retrying after 5 seconds", thread_num)
            sleep(5)

def fetch_job(conn_soc):
    while 1:
        try:
            conn_soc.sendall(
                bytes(f"JOB,{USERNAME},{DIFFICULTY}", encoding="utf8")
            )
            job = conn_soc.recv(128).decode().split(',')
            return str(job[0]), str(job[1]), int(job[2])
        except:
            sleep(3)
    
def fetch_block_hash(base:str, target:str, diff:int): 
    start_time = time()
    base = sha1(base.encode('ascii'))
    attemp = None
    for res in range(100 * diff + 1):
        attemp = base.copy()
        attemp.update(str(res).encode('ascii'))
        validator = attemp.hexdigest()
        if target == validator:
            process_time = time()-start_time
            hashrate = (res/process_time)/1000
            return res, round(hashrate, 2)

def send_block_hash(conn_soc, result, hashrate):
    result_message = f'{result},{hashrate},Dino Miner V{VER},{WORKER}'
    while 1:
        conn_soc.sendall(bytes(result_message, encoding='utf8'))
        start_time = datetime.now()
        feedback = conn_soc.recv(64).decode().rstrip('\n')
        ping = int((datetime.now()-start_time).microseconds / 1000)
        retval = 1 if feedback == "GOOD" else 2 if feedback == "BLOCK" else 3
        return retval, ping


def main(thread_num):
    logger(1, f"Miner {WORKER} Thread/{thread_num} Initializing . . . \n", thread_num)
    NODE_DETAIL = fetch_node(thread_num)

    ### MINING SECTION ###
    while 1:
        try:
            conn_soc = fetch_socket(NODE_DETAIL, thread_num)
            while 1:
                base, target, diff = fetch_job(conn_soc)
                result, hashrate = fetch_block_hash(base, target, diff)
                status, ping = send_block_hash(conn_soc, result, hashrate)
                if status == 1 or status == 2:
                    if status == 1:
                        msg = f"Accepted share, {hashrate} kH/s, {ping}ms"
                    else:
                        msg = f"Found Block, {hashrate}kH/s, {ping}ms"
                    logger(0, msg, thread_num)
                else:
                    logger(9, f'Rejected Share, Block {target}', thread_num)
        except KeyboardInterrupt:
            logger(1, "Terminating Childs", thread_num)
            for p in multiprocessing.active_children():
                p.kill()
                sleep(1)
            print()
            logger(2, "Application interrupted by SIGTERM", thread_num)
            return
        except Exception:
            logger(2, "Miner failed, retrying after 15 seconds", thread_num)
            sleep(15)
            del conn_soc            

    return


if __name__ == "__main__":
    try:
        Processes = []
        for i in range(THREADS_COUNT):
            proc = multiprocessing.Process(target=main, args=[i+1])
            proc.start()
            Processes.append(proc)
            logger(1, f"Thread {i+1}/{THREADS_COUNT} Started")
            sleep(1)
        for i in Processes:
            i.join()
    except KeyboardInterrupt:
        logger(1, "Terminating Childs")
        for p in multiprocessing.active_children():
            p.kill()
            sleep(1)
        print()
        logger(2, "Application interrupted by SIGTERM")
        
        # os.execl(sys.executable, sys.executable, *sys.argv)