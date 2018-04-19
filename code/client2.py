"""
    Simple client that sends some commands.
    Test ZeroM

    Andrew Turpin
    Wed 18 Apr 2018 19:50:08 AEST
"""

import socket
import json
import time

from client1 import doOne

    # dummy player for testing 
p = """ 
class Player:
    def take_turn(self, data, victory): 
        d = {k:100.0 for k in data}
        d[victory[1]] = 0.0
        return d
"""

doOne(json.dumps({"cmd":"TEST", "syn":0, "name":"ZM", "data":p, "data2":p, "vt1":"ZeroM", "vt2":"SumNeg", "same_col":True}))
doOne(json.dumps({"cmd":"ADD", "syn":0, "name":"Andrew_0", "data":p}))

#p = Player()
#print(p.take_turn({k:0 for k in 'abcde'}, ("ZeroM", "a")))
