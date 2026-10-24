import tempfile
import unittest
from pathlib import Path

from database import CardStore, POINTS_PER_PACK, STARTER_CARDS


class CardStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = CardStore(str(Path(self.tempdir.name) / "test.sqlite3"))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_profile_starts_at_zero(self):
        profile = self.store.get_profile(123, 456)
        self.assertEqual(profile["points_total"], 0)
        self.assertEqual(profile["progress"], 0)
        self.assertEqual(profile["packs"], 0)

    def test_pack_is_awarded_at_threshold_and_remainder_carries(self):
        self.assertEqual(self.store.credit_points(1, 2, POINTS_PER_PACK - 10, 9, "test"), 0)
        self.assertEqual(self.store.credit_points(1, 2, 25, 9, "test"), 1)
        profile = self.store.get_profile(1, 2)
        self.assertEqual(profile["packs"], 1)
        self.assertEqual(profile["progress"], 15)
        self.assertEqual(profile["points_total"], POINTS_PER_PACK + 15)

    def test_cannot_open_pack_without_one(self):
        self.assertFalse(self.store.consume_pack(5, 6))
        self.assertEqual(self.store.get_profile(5, 6)["packs"], 0)

    def test_pack_consumption_is_single_use(self):
        self.store.credit_points(5, 6, POINTS_PER_PACK, 7, "test")
        self.assertTrue(self.store.consume_pack(5, 6))
        self.assertFalse(self.store.consume_pack(5, 6))

    def test_open_pack_with_card_is_atomic_and_single_use(self):
        card = STARTER_CARDS[0]
        self.store.credit_points(8, 9, POINTS_PER_PACK, 7, "test")
        opened = self.store.open_pack_with_card(8, 9, card)
        self.assertIsNotNone(opened)
        self.assertEqual(opened["name"], card["name"])
        self.assertIsNone(self.store.open_pack_with_card(8, 9, card))
        profile = self.store.get_profile(8, 9)
        self.assertEqual(profile["packs"], 0)
        self.assertEqual(profile["card_count"], 1)


    def test_trade_accept_swaps_card_ownership(self):
        card_a = self.store.add_card(10, 20, STARTER_CARDS[0])
        card_b = self.store.add_card(10, 21, STARTER_CARDS[2])
        offer = self.store.create_trade(10, 20, 21, card_a["instance_id"], card_b["instance_id"])
        self.store.accept_trade(10, offer["trade_id"], 21)
        self.assertEqual(self.store.get_collection(10, 20)[0]["instance_id"], card_b["instance_id"])
        self.assertEqual(self.store.get_collection(10, 21)[0]["instance_id"], card_a["instance_id"])

    def test_cards_in_pending_trade_are_locked(self):
        a = self.store.add_card(10, 20, STARTER_CARDS[0])
        b = self.store.add_card(10, 21, STARTER_CARDS[2])
        c = self.store.add_card(10, 22, STARTER_CARDS[1])
        self.store.create_trade(10, 20, 21, a["instance_id"], b["instance_id"])
        with self.assertRaises(ValueError):
            self.store.create_trade(10, 20, 22, a["instance_id"], c["instance_id"])

    def test_only_recipient_can_accept_trade(self):
        a = self.store.add_card(10, 20, STARTER_CARDS[0])
        b = self.store.add_card(10, 21, STARTER_CARDS[2])
        offer = self.store.create_trade(10, 20, 21, a["instance_id"], b["instance_id"])
        with self.assertRaises(ValueError):
            self.store.accept_trade(10, offer["trade_id"], 99)


    def test_card_lookup_and_collection_pagination(self):
        cards = [self.store.add_card(4, 5, card) for card in STARTER_CARDS[:3]]
        first_page = self.store.get_collection(4, 5, limit=2, offset=0)
        second_page = self.store.get_collection(4, 5, limit=2, offset=2)
        self.assertEqual(len(first_page), 2)
        self.assertEqual(len(second_page), 1)
        found = self.store.get_card(4, 5, cards[1]["instance_id"])
        self.assertEqual(found["instance_id"], cards[1]["instance_id"])
        self.assertIsNone(self.store.get_card(4, 99, cards[1]["instance_id"]))
        self.assertEqual(self.store.count_cards(4, 5), 3)

    def test_expired_trade_is_marked_expired_even_when_accept_fails(self):
        a = self.store.add_card(10, 20, STARTER_CARDS[0])
        b = self.store.add_card(10, 21, STARTER_CARDS[2])
        offer = self.store.create_trade(10, 20, 21, a["instance_id"], b["instance_id"])
        with self.store.connect() as db:
            db.execute("UPDATE trades SET expires_at=datetime('now','-1 minute') WHERE trade_id=?", (offer["trade_id"],))
        with self.assertRaisesRegex(ValueError, "expired"):
            self.store.accept_trade(10, offer["trade_id"], 21)
        history = self.store.get_trade_history(10, 20)
        self.assertEqual(history[0]["status"], "expired")

    def test_duplicate_card_instances_are_allowed(self):
        card = STARTER_CARDS[0]
        first = self.store.add_card(3, 4, card)
        second = self.store.add_card(3, 4, card)
        self.assertNotEqual(first["instance_id"], second["instance_id"])
        self.assertEqual(self.store.get_profile(3, 4)["card_count"], 2)


if __name__ == "__main__":
    unittest.main()
