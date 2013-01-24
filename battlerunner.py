import sys
import re
import random
from collections import Counter

from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol
from twisted.protocols.basic import LineOnlyReceiver
from twisted.internet.defer import DeferredQueue, Deferred
from twisted.internet.error import ProcessTerminated, ProcessDone, ProcessExitedAlready


class BattleshipsProcessProtocol(LineOnlyReceiver, ProcessProtocol):
    def __init__(self, name):
        self.name = name
        self.buf = ''
        self.queue = DeferredQueue()
        self.on_crash = Deferred()
        self.err = ''

    def errReceived(self, data):
        self.err += data

    def outReceived(self, data):
        self.buf += data
        lines = self.buf.split('\n')
        self.buf = lines[-1]
        for l in lines[:-1]:
            self.lineReceived(l)

    def lineReceived(self, line):
        mo = re.match(r'^([A-Z])(\d+)$', line, flags=re.I)
        if mo:
            col = ord(mo.group(1).upper()) - 64
            row = int(mo.group(2))
            self.queue.put((col, row))

    def processExited(self, status):
        if self.err:
            print self.name, "crashed with error:"
            print self.err
        self.on_crash.errback(status)

    def getMove(self):
        return self.queue.get()

    def sendResult(self, result):
        self.transport.write(result + '\n')

    def close(self):
        try:
            self.transport.signalProcess('TERM')
        except ProcessExitedAlready:
            pass

HIT = 'h'
MISS = 'm'
WIN = 'w'
SUNK = 's'



class Grid(object):
    SIZE = 10
    SHIPS = {
        1: 1,
        2: 2,
        3: 1,
        4: 1
    }

    def coord_in_grid(self, x, y):
        return 0 < x <= self.GRID_SIZE and 0 < y <= self.GRID_SIZE

    def __init__(self):
        self.grid = {}  # state of the board
        self.healths = {}  # healths of each ship
        self.place_ships()

    def place_ships(self):
        id = 1
        for length, num in self.SHIPS.items():
            for s in range(num):
                self.place_ship(id, length)
                id += 1

    def place_ship(self, id, length):
        while True:
            orient = random.randint(0, 1)
            if orient == 0:
                x1 = random.randint(1, self.SIZE - length + 1)
                y = random.randint(1, self.SIZE)
                for x in range(x1, x1 + length):
                    if self.grid.get((x, y)):
                        break
                else:
                    for x in range(x1, x1 + length):
                        self.grid[x, y] = (id, False)
                    break
            else:
                x = random.randint(1, self.SIZE)
                y1 = random.randint(1, self.SIZE - length + 1)
                for y in range(y1, y1 + length):
                    if self.grid.get((x, y)):
                        break
                else:
                    for x in range(y1, y1 + length):
                        self.grid[x, y] = (id, False)
                    break
        self.healths[id] = length

    def sink_ship(self, id):
        """Remove a ship from the board."""
        l = 0
        for k, v in self.grid.items():
            if v[0] == id:
                del self.grid[k]
                l += 1
        return l

    def attack(self, x, y):
        """Attack the grid cell at x, y."""
        c = self.grid.get((x, y))
        if c is None:
            return MISS
        id, hit = c
        if not hit:
            health = self.healths[id] - 1
            if health > 0:
                self.grid[x, y] = (id, True)
                self.healths[id] = health
            else:
                length = self.sink_ship(id)
                del self.healths[id]
                if not self.healths:
                    return WIN
                else:
                    return SUNK + '\n%d' % length
        return HIT


class Player(object):
    def __init__(self, id, script):
        self.id = id
        self.script = script
        self.grid = Grid()
        self.process = BattleshipsProcessProtocol(script)
        reactor.spawnProcess(self.process, sys.executable, args=['python', '-u', script])

    def __str__(self):
        return self.script

    def set_opponent(self, player):
        self.opponent = player
        player.opponent = self


class Game(object):
    MOVE_TIME = 10  # time each script has to compute a move

    def __init__(self, script1, script2):
        self.player1 = Player(1, script1)
        self.player2 = Player(2, script2)
        self.player1.set_opponent(self.player2)

        self.move = 1
        # toss for who goes first
        next_player = random.choice([self.player1, self.player2])
        self.wait_move(next_player)

        self.result = Deferred()

    def wait_move(self, player):
        d = player.process.getMove()
        self.forfeit_timer = reactor.callLater(self.MOVE_TIME, self.forfeit, player)
        d.addCallback(self.on_move, player)
        player.process.on_crash.addErrback(self.on_crash, player)

    def deliver_result(self, winner, outcome):
        if self.result.called:
            return
        self.result.callback((winner, outcome))

    def on_crash(self, failure, player):
        failure.trap(ProcessTerminated, ProcessDone)

        winner = player.opponent.script
        if isinstance(failure.value, ProcessTerminated):
            outcome = '%s died with code %s' % (player, failure.value.exitCode)
        else:
            outcome = '%s exited' % player
        self.deliver_result(winner, outcome)

    def on_move(self, move, player):
        self.forfeit_timer.cancel()
        self.move += 1
        result = player.opponent.grid.attack(*move)
#        print player, move, '->', result
        if result == WIN:
            outcome = "Moves: %d" % (self.move // 2)
            self.deliver_result(player.script, outcome)
            player.process.close()
            player.opponent.process.close()
        else:
            player.process.sendResult(result)
            self.wait_move(player.opponent)

    def forfeit(self, player):
        outcome = "%s forfeited for taking more than %d seconds." % (player, self.MOVE_TIME)
        winner = player.opponent.script
        self.deliver_result(winner, outcome)
        player.process.close()
        player.opponent.process.close()


class GameRunner(object):
    CONCURRENCY = 20
    def __init__(self, script1, script2, games=1000):
        self.script1 = script1
        self.script2 = script2
        self.games = games
        self.started = 0
        self.finished = 0
        self.tally = Counter()
        for i in range(self.CONCURRENCY):
            self.start_game()

    def start_game(self):
        self.started += 1
        g = Game(self.script1, self.script2)
        g.result.addCallback(self.on_result)

    def on_result(self, result):
        self.finished += 1
        winner, outcome = result
        self.tally[winner] += 1
        print winner, outcome
        if self.finished >= self.games:
            self.print_final_result()
            reactor.stop()
        elif self.started < self.games:
            self.start_game()

    def print_final_result(self):
        for k in [self.script1, self.script2]:
            w = self.tally[k]
            print '%s: %d wins (%0.1f%%)' % (k, w, w * 100.0 / self.games)

    
g = GameRunner('team_a.py', 'team_alpha.py')
reactor.run()