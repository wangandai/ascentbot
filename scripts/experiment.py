import models
from dotenv import load_dotenv
load_dotenv()

g = models.Guilds.load()
for guild in g.values():
    print("Guild: {}".format(guild.title))
    for e in guild.expeditions.values():
        print(e.title)
        for m in e.members:
            print(m.tg_handle)
        print("\n")
print(len(g.guilds))