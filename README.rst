Battlerunner
============

An engine to run Battleships attack AIs against one another.

Run iterated battleships attack AIs against one another.


Writing AIs
-----------

AIs are Python scripts that communicate over stdin/stdout using an ASCII
protocol. Python 3 scripts should include a shebang (``#!``) line at the top
containing the string ``python3`` to ensure they are executed with the correct
interpreter.

The script must output a coordinate as a string followed by a newline.
It must then read an outcome, which will be one of the strings, followed by
a newline:

* ``h`` - hit
* ``m`` - miss
* ``s`` - sunk (followed by length, see below)
* ``w`` - game over

In the case that the outcome is ``s``,  the line will be followed by the length
of ship sunk, as a decimal string, followed by another newline.

The grid
''''''''

The grid is a 10x10 grid of cells. Cells are lettered ``A`` to ``J`` on one
axis and ``1`` to ``10`` on the other axis.

Coordinates are written by concatenating the letter and the number, eg. ``A1``.

Ship placement
''''''''''''''

Ship placement is nuot under control of the AI; ships are placed by the runner
alone.

These are the ships that exist in each enemies grid:

+------------+---------+-------------------+
| Type       | Length  | Number per player |
+============+=========+===================+
| Destroyer  | 2       | 1                 |
+------------+---------+-------------------+
| Submarine  | 3       | 2                 |
+------------+---------+-------------------+
| Battleship | 4       | 1                 |
+------------+---------+-------------------+
| Carrier    | 5       | 1                 |
+------------+---------+-------------------+
