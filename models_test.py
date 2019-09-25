import unittest
import models as m
from datetime import datetime


class TelegramInfoTest(unittest.TestCase):
    def test_equality(self):
        tg1 = m.TelegramInfo()
        tg2 = m.TelegramInfo()
        tg3 = m.TelegramInfo()

        tg1.id = "1"
        tg2.id = "1"
        tg3.id = "3"

        self.assertEqual(True, tg1 == tg2)
        self.assertEqual(False, tg1 == tg3)


class PlayerTest(unittest.TestCase):
    def test_equality(self):
        p1 = m.Player()
        p2 = m.Player()
        p3 = m.Player()

        p1.telegram.id = "1"
        p2.telegram.id = "1"
        p3.telegram.id = "3"

        self.assertEqual(True, p1 == p2)
        self.assertEqual(False, p1 == p3)


class ExpeditionTest(unittest.TestCase):
    def test_set_time(self):
        e1 = m.Expedition("test")

        e1.set_time("15:00")

        self.assertEqual(e1.time, datetime.strptime("15:00", "%H:%M").time())


class ExpeditionMemberTest(unittest.TestCase):
    def test_equality(self):
        m1 = m.ExpeditionMember()
        m2 = m.ExpeditionMember()
        m3 = m.ExpeditionMember()

        m1.label = "l1"
        m1.tg_handle = "t1"
        m2.label = "l1"
        m2.tg_handle = "t1"
        m3.label = "l2"
        m3.tg_handle = "t1"

        self.assertEqual(True, m1 == m2)
        self.assertEqual(False, m1 == m3)


class GuildTest(unittest.TestCase):
    def test_expedition(self):
        g = m.Guild()
        e_title = "test"
        g.new_expedition(e_title)

        e1 = g.get_expedition(e_title)
        self.assertEqual(e1.title, e_title)

        g.checkin_expedition(e_title, 123, "player1")
        self.assertEqual(1, len(e1.members))

        g.checkout_expedition(e_title, 123, "player1")
        self.assertEqual(0, len(e1.members))

        g.checkin_expedition(e_title, 123, "player1", "label1")
        self.assertEqual(1, len(e1.members))

        g.checkin_expedition(e_title, 123, "player1", "label2")
        self.assertEqual(2, len(e1.members))

        g.checkin_expedition(e_title, 123, "player1")
        self.assertEqual(3, len(e1.members))

        g.checkin_expedition(e_title, 123, "player1", "label1")
        self.assertEqual(3, len(e1.members))

        g.checkout_expedition(e_title, 123, "player1", "label1")
        self.assertEqual(2, len(e1.members))

        g.set_expedition_time(e_title, "15:00")
        self.assertEqual(datetime.strptime("15:00", "%H:%M").time(), e1.time)

        g.delete_expedition(e_title)
        self.assertEqual(g.get_expedition(e_title), None)


if __name__ == '__main__':
    unittest.main()
