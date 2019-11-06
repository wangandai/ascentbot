import database
import json

s = database.Storage()
g = s.loadfile("guilds.prd.json", "json")
print(json.dumps(g, indent=4))