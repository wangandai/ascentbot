from models import *
import json
import unittest
import database


def obj_to_json(o):
    try:
        return o.__dict__
    except AttributeError:
        print("Could not serialize: {}".format(o))
        return None


class TestStringMethods(unittest.TestCase):
    def test_players(self):
        member1 = Player("id1", "handle1", "lal1")
        member2 = Player("id1", "handle1", "lal1")
        self.assertEqual(member1, member2)

    def test_serialization(self):
        # create local storage
        storage = database.Storage(storage_type="local")

        # Setup some basic guild info
        g = Guild()
        g.title = "guild1"
        g.new_expedition("test1", "1200")
        g.checkin_expedition("test1", "mem1", "han1", "lab1")
        g.checkin_expedition("test1", "mem2", "han2", "lab2")
        g.chat_id = 12341234
        g.pinned_message_id = 4123413
        g.fort_mark("tg_id1", "handle1", "label1")
        g.update_fort_history()
        g.fort_mark("tg_id1", "handle1", "label1")
        g.fort_unmark("tg_id1", "handle1", "label1")
        g.fort_mark("tg_id1", "handle1", "label1")

        # Test
        d = json.dumps(g, default=obj_to_json)
        f = Guild.from_json(json.loads(d))
        _f = json.dumps(f, default=obj_to_json)
        self.assertEqual(_f, d)

        gs = Guilds(storage=storage)
        gs.set("23452", g)

        gs.save()
        gs2 = Guilds.load(storage=storage)

        # Test expedition info is retained
        g2 = gs2.get("23452")
        g2.checkout_expedition("test1", "mem1", "han1", "lab1")
        self.assertEqual(len(g2.get_expedition("test1").members), 1)

        # Test fort info is retained
        attendance = g2.get_attendance_today("tg_id1", "handle1", "label1")
        self.assertTrue(attendance)


if __name__ == '__main__':
    unittest.main()