import database
import json

FILENAME = "exped_default.json"
with open(FILENAME, 'r') as f:
    content = json.load(f)
    s = database.Storage()
    g = s.savefile(FILENAME, "json")