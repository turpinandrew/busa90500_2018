"""
    A class to hold data and run a single game.

    Andrew Turpin
    Fri 30 Mar 2018 15:02:55 AEDT
"""
import random
from scipy import stats 
import numpy as np
from collections import defaultdict

class Game:
    names = [ "Amy", "Andrew", "Angela", "Bernie", "Biying", "Bushra",
	      "Carrie", "Claire", "Clarence", "Dane", "Dengke",
	      "Erika", "Ernest", "Hong", "Hugh", "Inno", "Iris",
	      "Jennifer", "Jiahui", "Jiaming", "Jianan", "Jianfeng",
	      "Jingyu", "Joy", "Juerong", "Junming", "Junyi",
	      "Kritika", "Maggie", "Mark", "Monica", "Nancy",
	      "Noorida", "Peggy", "Peter", "Priyadarshini", "Qingqing",
	      "Ryan", "Ryan", "Samuel", "Shaojuan", "Shiwen",
	      "Shufan", "Simon", "Sky", "Suchi", "Thomas", "Tony",
	      "Venkat", "Viplav", "Vivienne", "Wendee", "Xiaoyu",
	      "Xinrong", "Xue", "Yanjun", "Yan", "Yijin", "Yinghao",
	      "Yingrang", "Yin", "Yiwen", "Yoke", "Yuan", "Yunong",
	      "Zichen"]

    victory_types = ['Max', 'Min', 'Linear', "Quadratic", "ZeroM", "SumNeg", "SumPos"]

    def __init__(self, num_rounds=10, num_cols=5, vic_type1=None, vic_type2=None, same_col=False):
        """ Randomly choose num_cols column names and the two 
            victory conditions for the game (if vic_type == None).

            vic_type - an index into Game.victory_types to fix criteria for the game.
                       If None, randomly chosen.
            same_col - if True, then choose the same victory column for both players, else random.
        """
        self.num_rounds = num_rounds
        self.num_cols = num_cols
        self.col_names = random.sample(Game.names, k=num_cols)

            # select two victory types and columns
        if vic_type1 is None:
            self.vic_types = [random.sample(Game.victory_types)]
        else:
            self.vic_types = [Game.victory_types[vic_type1]]

        if vic_type2 is None:
            self.vic_types.append(random.sample(Game.victory_types))
        else:
            self.vic_types.append(Game.victory_types[vic_type2])

        if same_col:
            c = random.sample(self.col_names, k=1)[0]
            self.vic_cols = [c,c]
        else:
            self.vic_cols = random.sample(self.col_names, k=2)

    def check_condition(self, data, player_index):
        """Return True if vic_*[player_index] is true for data, False otherwise.
           data : dictionary with keys self.col_names, list of floats as values
           player_index : 0 or 1 for p1 or p2 to index self.vic_types and self.vic_cols.
        """
        if self.vic_types[player_index] == "Max":
            maxes = defaultdict(int)  # count frequency of values
            for k in data:
                for v in data[k]:
                    maxes[v] += 1
            most = -1024
            for v in sorted(maxes.keys(), reverse=True): # find max unique
                if maxes[v] == 1:
                    most = v
                    break
            maxes = [k for k,v in data.items() if most in v]
            return len(maxes) == 1 and self.vic_cols[player_index] == maxes[0]
        elif self.vic_types[player_index] == "Min":
            mins = defaultdict(int)  # count frequency of values
            for k in data:
                for v in data[k]:
                    mins[v] += 1
            least = 1024
            for v in sorted(mins.keys()): # find min unique
                if mins[v] == 1:
                    least = v
                    break
            mins = [k for k,v in data.items() if least in v]
            return len(mins) == 1 and self.vic_cols[player_index] == mins[0]
        elif self.vic_types[player_index] == "Linear":
            ys = data[self.vic_cols[player_index]]
            r,p = stats.pearsonr(range(len(ys)), ys)
            return p < 0.05 and r > 0.9
        elif self.vic_types[player_index] == "Quadratic":
            ys = data[self.vic_cols[player_index]]
            ys = np.sqrt(ys - np.min(ys))
            r,p = stats.pearsonr(range(len(ys)), ys)
            return p < 0.05 and r > 0.9
        elif self.vic_types[player_index] == "ZeroM":
            return abs(np.mean(data[self.vic_cols[player_index]])) < 0.000001
        elif self.vic_types[player_index] == "SumNeg":
            return sum(data[self.vic_cols[player_index]]) < 0
        elif self.vic_types[player_index] == "SumPos":
            return sum(data[self.vic_cols[player_index]]) > 0
        else:
            raise ValueError('Unknown victory type in Game.check_condition().')

    def run_game(self, p1, p2):
        """Run a game of p1 vs p2.
           Return lots of stuff... 0 for draw, or 1 or 2 for winner.
        """
        message = ""
        could_win = [True, True]  # can each player win?
        data = {k:[0.0] for k in self.col_names}
        for rnd in range(self.num_rounds):
            p1_row = p1.take_turn(data, (self.vic_types[0], self.vic_cols[0]))
            p2_row = p2.take_turn(data, (self.vic_types[1], self.vic_cols[1]))

                # append each row, looking for missing key or non-float value
            for p,row in [(0, p1_row), (1, p2_row)]:
                for k in data:
                    if k not in row or not isinstance(row[k], float):
                        could_win[p] = False
                        message += "Player {} returned a row that was not valid.\n".format(p+1)
                    else:
                        data[k].append(round(row[k],5))

        if message == '':
            message = 'gg\n'

        if all(could_win):
            wins = [self.check_condition(data, i) for i in range(2)]
            if all(wins) or not any(wins):
                winner = 0
            elif wins[0]:
                winner = 1
            else:
                winner = 2
        elif could_win[0]:
            winner = 1
        else:
            winner = 2

        return [data, 
                (str(p1), self.vic_types[0], self.vic_cols[0]), 
                (str(p2), self.vic_types[1], self.vic_cols[1]), 
                winner,
                message
               ]
