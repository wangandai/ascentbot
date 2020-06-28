import database
import json


def relevant(guild):
#    return not guild["stopped"] and guild["chat_id"] < 0
    return guild["chat_id"] < 0


s = database.Storage()
g = s.loadfile("guilds.prd.json", "json")
guilds = g["guilds"]
filtered = [guilds[chat_id] for chat_id in guilds.keys() if relevant(guilds[chat_id])]
print(json.dumps(filtered, indent=4))
