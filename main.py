DELIMITER = '\t'
HEADERS = ['ign', 'job' 'lvl', 'wep', 'wep2', 'boss']


class Player:

    def __init__(self, line):
        stats = line.split(DELIMITER)

        for i, header in enumerate(HEADERS):
            try:
                setattr(self, header, stats[i])
            except IndexError:
                setattr(self, header, None)


players = []

with open('members.csv', 'r') as f:
    for line in f.readlines()[1:]:
        players.append(Player(line))

print([p.ign for p in players])