"""
    Run a tournament.

    Server code taken from 
    https://www.binarytides.com/python-socket-server-code-example/

    Server receives a JSON object with name:values as follows with "EOM" appended
        "cmd": {"ADD" | "DEL" | "PING" | "TEST"}
        "name": "team name"      # used in ADD and DEL
        "syn": syndicate number  # only used for ADD
        "data": "python script"  # only used for ADD and DEL 
        "vt1": vic_type          # only used for TEST
        "vt2": vic_type          # only used for TEST
        "data2": python script 2 # only used for TEST
        "same_col": True/False   # only used for TEST

    Server sends back a message terminated by \n
        SUCCESS\n         # for ADD, DEL, PING
        SUCCESS result\n  # for TEST
        ERR ...\n
"""
from game import Game
import socket, sys, imp
from threading import Lock
from _thread import start_new_thread
import json
import time
import random
import numpy as np
import yapf
import os
from datetime import datetime
 
HOST = 'localhost'   # Symbolic name, meaning all available interfaces
#HOST = '128.250.106.25' 
PORT = 5002         # Arbitrary non-privileged port

SDIR = "mbusa"
E_FILE = "e.html"

    # list of current players and their scripts: tuple (name, syn, script, wins, loses)
players = []
players_lock = Lock()
PLAYER_TUPLE_NAME = 0   # indexes into the tuples in players
PLAYER_TUPLE_SYN  = 1
PLAYER_TUPLE_CODE = 2
PLAYER_TUPLE_WINS = 3
PLAYER_TUPLE_LOSSES = 4

def do_test(data, conn):
    """Run a single game with victory_types data["vt1"] and data["vt2"] 
       and return result as a JSON object.
    """
    if "vt1" not in data or "vt2" not in data:
        conn.send("ERR: data needs keys 'vt1' and 'vt2' for TEST\n".encode('utf-8'))
        return

    if "data" not in data or "data2" not in data:
        conn.send("ERR: data needs keys 'data' and 'data2' for TEST\n".encode('utf-8'))
        return

    if data["vt1"] not in Game.victory_types:
        conn.send("ERR: victory type {} doesn't exist for TEST\n".format(data["vt1"]).encode('utf-8'))
        return

    if data["vt2"] not in Game.victory_types:
        conn.send("ERR: victory type {} doesn't exist for TEST\n".format(data["vt2"]).encode('utf-8'))
        return
        
    same_col = False
    if "same_col" in data:
        same_col = data["same_col"]

    vt1 = Game.victory_types.index(data["vt1"])
    vt2 = Game.victory_types.index(data["vt2"])
    g = Game(vic_type1=vt1, vic_type2=vt2, same_col=same_col)

    p1_module = imp.new_module('p1_module')
    p2_module = imp.new_module('p2_module')
    try:
        exec(data["data"], p1_module.__dict__)
        exec(data["data2"], p2_module.__dict__)
        result = g.run_game(p1_module.Player(), p2_module.Player())
        if len(result) == 2:
            raise Exception("Player {} failed: {}".format(result[0], result[1]))
    except Exception as msg:
        conn.send("ERR: couldn't run game for TEST: {}\n".format(msg).encode('utf-8'))
    else:
        conn.send("SUCCESS {}\n".format(json.dumps(result)).encode('utf-8'))

def add_player(d):
    """Return message for server. 
        d - dictionary with "data" "syn" and "name"
    """
    try:
        d["syn"] = int(d["syn"])
        if d["syn"] not in range(13):
            return("ERR: data['syn'] not in range [1,12]\n".encode('utf-8'))
        if "data" not in d:
            return("ERR: data does not have key 'data'\n".encode('utf-8'))
    except KeyError:
        return("ERR: data does not have key 'syn'\n".encode('utf-8'))
    except ValueError:
        return("ERR: data['syn'] is not an integer\n".encode('utf-8'))

    if "name" not in d:
        d["name"] = d["syn"]

    players_lock.acquire()

    if any([d["name"] == n and d["syn"] == s for n,s,_,_,_ in players]):
        players_lock.release()
        return("ERR: Player already exists\n".encode('utf-8'))

    players.append((d["name"], d["syn"], d["data"], 0, 0)) 
    players_lock.release()

    fname = "{}/{}_{}.py".format(SDIR, d["name"], d["syn"])
    with open(fname, "w") as f:
        f.write(d["data"])
    try:
        yapf.FormatFiles([fname], [(1,100000)], in_place=True)  # assumes no more than 100000 lines of code
    except Exception:
        print("Cannot yapf {}\n".format(fname)) 

    print("ADDED {1}_{0}".format(d["syn"], d["name"]))
    return("SUCCESS\n".encode('utf-8'))

def delete_player(d):
    """ d = {"name":..., "syn":...}
        Returns a message to send to client.
        Assumes players is locked
    """
    if "name" not in d or "syn" not in d:
        return "ERR: missing name or syn in DEL\n".encode('utf-8')

    global players
    names = [p[PLAYER_TUPLE_NAME] for p in players]
    if d["name"] in names:
        print("Deleting {}".format(d["name"]))
        i = names.index(d["name"]) 
        players.pop(i)

        fname = "{}/{}_{}.py".format(SDIR, d["name"], d["syn"])
        try:
            os.remove(fname)
        except OSError:
            msg = "ERR: couldn't delete file\n".encode('utf-8')
        else:
            msg = "SUCCESS\n".encode('utf-8')
            print('DELETED {} {}'.format(d["name"], d["syn"]))
    else:
        msg = "ERR: name {} doesn't exist\n".format(d["name"]).encode('utf-8')

    return msg

def clientthread(conn):
    """Loop reading the code then close.
       If name does not exist for ADD, use syndicate number.
       DEL by name.
    """
    try:
        data = ''
        while data == '' or data[-3:] != "EOM":
            data += conn.recv(1024).decode('utf-8')

        d = json.loads(data[:-3])  # strip "EOM"
        if "cmd" not in d:
            conn.send("ERR: No cmd in {} \n".format(data).encode('utf-8'))
        else:
            if d["cmd"] == "PING":
                conn.send("SUCCESS\n".encode('utf-8'))
            elif d["cmd"] == "ADD":
                msg = add_player(d)
                conn.send(msg)
            elif d["cmd"] == "DEL":
                print("DELETE command")
                if "name" not in d:
                    conn.send("ERR: Missing name in {} \n".format(data).encode('utf-8'))
                else:
                    players_lock.acquire()
                    msg = delete_player(d)
                    conn.send(msg)
                    players_lock.release()
            elif d["cmd"] == "TEST":
                res = do_test(d, conn)

        conn.close()
    except Exception as msg:
        print(msg)
        print("Data:")
        print(data)

def check_all_on_score_board(score_board):
    """ Check score board has all the players.
        Note: may change score_board!
        Assumes players is locked.
    """
    global players
    for p in players:
        k = (p[PLAYER_TUPLE_NAME], p[PLAYER_TUPLE_SYN]) 
        if k not in score_board:
            n = len(Game.victory_types)
            score_board[k] = {(p[PLAYER_TUPLE_NAME], p[PLAYER_TUPLE_SYN]):[np.zeros((n,n)) for i in [1,2,3]] for p in players}
            for k2 in score_board:
                score_board[k2][k] = [np.zeros((n,n)) for i in [1,2,3]]

def check_no_extras_on_score_board(score_board):
    """ Check score board does not have deleted players.
        Note: may change score_board!
        Assumes players is locked.
    """
    global players
    to_remove = []
    for k in score_board:
        if not any((p[PLAYER_TUPLE_NAME], p[PLAYER_TUPLE_SYN]) == k for p in players):
            to_remove.append(k)

    for k in to_remove:
        score_board.pop(k, None) 
        for kk in score_board:    # remove from rows too
            score_board[kk].pop(k, None)

def choose_game(score_board):
    """Find the pairing that has played the least (ie sum of wins and loss count smallest).
       @return (key1, key2, index1 into game.victory_types, index2) to index score_board for pairing.
               (None,None,None,None) if no game available
        Assumes players is locked.
    """
    global players
    if len(players) < 2:
        return (None, None, None, None)

    k1 = (players[0][PLAYER_TUPLE_NAME], players[0][PLAYER_TUPLE_SYN])
    k2 = (players[1][PLAYER_TUPLE_NAME], players[1][PLAYER_TUPLE_SYN])
    min_num_games = sum([score_board[k1][k2][i][0][0] for i in [0,1,2]])
    min_keys = (k1, k2, 0, 0)
    for k1 in score_board:
        for k2 in score_board:
            if k1 != k2 and k1[1] != k2[1] :
                for index1 in range(len(Game.victory_types)):
                    for index2 in range(len(Game.victory_types)):
                        s = sum(wld[index1][index2] for wld in score_board[k1][k2])
                        if s < min_num_games:
                            min_num_games = s
                            min_keys = (k1, k2, index1, index2)
    return min_keys

    """
    p1 = random.randint(0, len(players)-1)
    p2 = random.randint(0, len(players)-1)
    v1 = random.randint(0, len(Game.victory_types)-1)
    v2 = random.randint(0, len(Game.victory_types)-1)
    k1 = (players[p1][PLAYER_TUPLE_NAME], players[p1][PLAYER_TUPLE_SYN])
    k2 = (players[p2][PLAYER_TUPLE_NAME], players[p2][PLAYER_TUPLE_SYN])
    return (k1, k2, v1, v2)
    """

def print_score_board(score_board):
    """Pretty cross table of round robin in order of total wins.
       @param score_board is dict of dict of [[win],[losses],[draw]]
    """
    def line():
        print("{}+".format("".join(["-"]*18)), end="")
        for k in keys:
            print("{}+".format("".join(["-"]*18)), end="")
        print("")

    keys = score_board.keys()
    wins = [sum([np.sum(wld[0]) for _,wld in score_board[k].items()]) for k in keys]
    keys = [x for _,x in sorted(zip(wins,keys), reverse=True)]

    line()

    print("".join(["{:18}|".format(" ")] + ["{:>16}{:2}|".format(k[0],k[1]) for k in keys]))

    line()

    for k1 in keys:
        print("{:>16}{:2}|".format(k1[0], k1[1]), end="")
        wins = losses = draws = 0
        for k2 in keys:
            w = np.sum(score_board[k1][k2][0])
            l = np.sum(score_board[k1][k2][1])
            d = np.sum(score_board[k1][k2][2])
            print("{:>5}/{:>5}/{:>6}|".format(w,l,d), end="")
            wins   += w
            losses += l
            draws  += d

        print("{:>5}/{:>5}/{:>6}".format(wins, losses, draws))

    line()

def print_leader_board(score_board):
    """Pretty each teams wins/losses/draws in order of total wins.
       @param score_board is dict of dict of [[win],[losses],[draw]]
              primary key (name, syn) 
    """
    keys = score_board.keys()
    wins = {k:sum((sum((sum(i) for i in wld[0])) for _,wld in score_board[k].items())) for k in keys}
    loss = {k:sum((sum((sum(i) for i in wld[1])) for _,wld in score_board[k].items())) for k in keys}
    for k in loss:
        if loss[k] == 0:
            loss[k] = 0.1
    wl = { k:(wins[k] / loss[k]) for k in keys }
    keys = [k for _,k in sorted([(v,k) for k,v in wl.items()], reverse=True)]

    s = ["<html>\n<body>\n<h3>BUSA90500 Programming Assignment</h3>"]
    s = ["<p>Games played: {}".format(sum(wins.values()))]
    s += ['<table style="text-align:center">'] 

    n = len(Game.victory_types)
    for k in keys:
        s += ['<tr><td style="border-bottom:1px solid black" colspan="100%"></td></tr>']

        s += ['<tr><td colspan="15" style="text-align:left">{:>16} ({:1}) win-loss-ratio={}</td></tr>'.format(k[0], k[1], wl[k])]
        s += ['<tr><td></td>']
        s += ['<td style="border-bottom:1px solid black" colspan="{}">Wins</td><td></td>'.format(len(Game.victory_types))]
        s += ['<td style="border-bottom:1px solid black" colspan="{}">Draws</td><td></td>'.format(len(Game.victory_types))]
        s += ['<td style="border-bottom:1px solid black" colspan="{}">Losses</td><td></td>'.format(len(Game.victory_types))]
        s += ['</tr>']
        s += ["<tr><td></td><td>{}".format("<td>".join(Game.victory_types))]
        s += ["<td></td><td>{}".format("<td>".join(Game.victory_types))]
        s += ["<td></td><td>{}</tr>".format("<td>".join(Game.victory_types))]
        ws = np.zeros((n,n), dtype="int")
        ds = np.zeros((n,n), dtype="int")
        ls = np.zeros((n,n), dtype="int")
        for k2 in keys:
            ws += np.array(score_board[k][k2][0]).astype(int)
            ds += np.array(score_board[k][k2][1]).astype(int)
            ls += np.array(score_board[k][k2][2]).astype(int)

        for row in range(n):
            s += ["<tr><td>{}</td>".format(Game.victory_types[row])]
            s += ["<td>", "<td>".join(map(str, ws[row]))]
            s += ["<td></td><td>", "<td>".join(map(str, ls[row]))]
            s += ["<td></td><td>", "<td>".join(map(str, ds[row])), "</tr>"]

    s += ["</table></body></html>"]

    with open('lb.html', "w") as f:
        f.write("\n".join(s))
    #print("\n".join(s))

def write_to_e(msg, player, action):
    """all are strings. msg<br>player written to column 2, action to column 3
    """
    with open(E_FILE, "a") as f:
        f.write("\n<tr><td>{}</td>".format(str(datetime.now())))
        f.write("<td>{}{}</td>".format(msg, player))
        f.write("<td>{}</td></tr>".format(action))

def run_games():
    """Thread running to randomly choose pairs from players and 
       run them against each other in a game.

       score_board is a dictionary indexed by (name, syn) keeping wins, losses and draws for that key.
    """
    score_board = {}  # key = (name, syn), value = { (name, syn): [wins for key, losses for key, draws for key]}
    while True:
        players_lock.acquire()
        check_all_on_score_board(score_board)
        check_no_extras_on_score_board(score_board)

        #print_score_board(score_board)
        print_leader_board(score_board)

        k1, k2, vic_type_index1, vic_type_index2 = choose_game(score_board)
        players_lock.release()
        if k1 is not None:
            print("{} ({}) vs {} ({})".format(k1, Game.victory_types[vic_type_index1], k2, Game.victory_types[vic_type_index2]))
            try:
                g = None
                p1_module = imp.new_module('p1_module')
                p2_module = imp.new_module('p2_module')
                players_lock.acquire()
                for p in players:
                    if (p[PLAYER_TUPLE_NAME], p[PLAYER_TUPLE_SYN]) == k1:
                        exec(p[PLAYER_TUPLE_CODE], p1_module.__dict__)
                    if (p[PLAYER_TUPLE_NAME], p[PLAYER_TUPLE_SYN]) == k2:
                        exec(p[PLAYER_TUPLE_CODE], p2_module.__dict__)
                players_lock.release()
                g = Game(vic_type1=vic_type_index1, vic_type2=vic_type_index2)
                if g:
                    players_exist = True
                    try:
                        pp = p1_module.Player()
                    except AttributeError as msg:
                        players_lock.acquire()
                        print(delete_player({"name": k1[0], "syn": k1[1]}))
                        players_lock.release()
                        write_to_e("No Player class.", k1, "Not started")
                        players_exist = False

                    try:
                        pp = p2_module.Player()
                    except AttributeError as msg:
                        players_lock.acquire()
                        print(delete_player({"name": k2[0], "syn": k2[1]}))
                        players_lock.release()
                        write_to_e("No Player class.", k2, "Not started")
                        players_exist = False

                    if players_exist:
                        result = g.run_game(p1_module.Player(), p2_module.Player())
                        print(result)
                        
                        if len(result) == 2:
                            if result[0] == 1:
                                players_lock.acquire()
                                _ = delete_player({"name": k1[0], "syn": k1[1]})
                                players_lock.release()
                                msg = k1
                            elif result[0] == 2: 
                                players_lock.acquire()
                                _ = delete_player({"name": k2[0], "syn": k2[1]})
                                players_lock.release()
                                msg = k2

                                if result[0] == 1:
                                    write_to_e(msg, result[1], Game.victory_types[vic_type_index1])
                                else:
                                    write_to_e(msg, result[1], Game.victory_types[vic_type_index2])
                            print(msg)
                        elif len(result) > 2:
                            if result[-2] == 1:
                                score_board[k1][k2][0][vic_type_index1][vic_type_index2] += 1  # win for k1
                                score_board[k2][k1][1][vic_type_index2][vic_type_index1] += 1  # loss for k2
                            elif result[-2] == 2:                      
                                score_board[k1][k2][1][vic_type_index1][vic_type_index2] += 1  # loss for k1
                                score_board[k2][k1][0][vic_type_index2][vic_type_index1] += 1  # win for k2
                            else:                                      
                                score_board[k1][k2][2][vic_type_index1][vic_type_index2] += 1  # draw for k1
                                score_board[k2][k1][2][vic_type_index2][vic_type_index1] += 1  # draw for k2
            except Exception as msg:
                print("Exception when trying to run a game")
                print(msg)
       
        try:
            players_lock.release()   # safety unlock
        except Exception:
            pass

        time.sleep(0.2)

def start_server():
        # open the socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((HOST, PORT))
    except socket.error as msg:
        print('Bind failed. Error Code : {} Message {}'.format(str(msg[0]), msg[1]))
        sys.exit()
         
    s.listen(10)
    
    start_new_thread(run_games, ())
    
        # load any existing players
    for file in os.listdir(SDIR):
        name = file[:-3]   # remove '.py'
        i = name.rfind('_')
        syn = name[i+1 : ]
        name = name[ : i]

        with open("{}/{}".format(SDIR,file)) as f:
            d = {'name':name, 'syn':syn, 'data':f.read()}
            msg = add_player(d)
            print(msg)
        
        # loop listening for connections.
    while True:
        conn, addr = s.accept()
        print('Connected with {} {}'.format(addr[0], addr[1]))
        start_new_thread(clientthread ,(conn,))
    
        players_lock.acquire()
        print("********************** {}".format(len(players)))
        print("\n".join([t[0] for t in players]))
        players_lock.release()

        time.sleep(0.1)

start_server()

###################################################
# Test run_games()
###################################################
#    # dummy player for testing 
#p = """ 
#class Player:
#    def __init__(self): pass
#    def take_turn(self, data, victory): return {k:1.1 for k in data}
#    def __repr__(self): return "Always 1.1"
#"""
#players.append(("T1", 1, p, 0, 0)) 
#players.append(("T2", 2, p, 0, 0)) 
#players.append(("T3", 2, p, 0, 0)) 
#
#run_games()
