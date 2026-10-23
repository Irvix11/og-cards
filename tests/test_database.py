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

    def test_duplicate_card_instances_are_allowed(self):
        card = STARTER_CARDS[0]
        first = self.store.add_card(3, 4, card)
        second = self.store.add_card(3, 4, card)
        self.assertNotEqual(first["instance_id"], second["instance_id"])
        self.assertEqual(self.store.get_profile(3, 4)["card_count"], 2)


if __name__ == "__main__":
    unittest.main()
