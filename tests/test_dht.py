"""Unit tests for the Kademlia routing table, DHT storage and helpers (no network needed).

Run from the project root:
    python tests/test_dht.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meshweaver.dht import (DHT, K, Contact, RoutingTable, hex_id,  # noqa: E402
                            key_to_id, new_node_id)

OWN = 1 << 100          # an arbitrary node id for the table under test


def contact_in_bucket(index, n=0):
    """A contact whose XOR distance from OWN has bit length index+1, so it lands in bucket `index`."""
    return Contact(OWN ^ ((1 << index) | n), "127.0.0.1", 9000 + n)


class HelperTests(unittest.TestCase):
    def test_key_to_id_is_deterministic_and_160_bit(self):
        a = key_to_id(b"task:1")
        self.assertEqual(a, key_to_id(b"task:1"))
        self.assertLess(a, 2 ** 160)
        self.assertNotEqual(a, key_to_id(b"task:2"))

    def test_hex_id_is_40_chars_and_reversible(self):
        self.assertEqual(len(hex_id(5)), 40)
        self.assertEqual(int(hex_id(123456789), 16), 123456789)

    def test_new_node_ids_are_random_and_in_range(self):
        a, b = new_node_id(), new_node_id()
        self.assertNotEqual(a, b)
        self.assertTrue(0 <= a < 2 ** 160)

    def test_contact_wire_round_trip(self):
        c = Contact(12345, "10.0.0.7", 9004)
        d = Contact.from_wire(c.to_wire())
        self.assertEqual((d.id, d.host, d.port), (12345, "10.0.0.7", 9004))


class RoutingTableTests(unittest.TestCase):
    def setUp(self):
        self.table = RoutingTable(OWN)

    def test_never_stores_itself(self):
        self.table.add(Contact(OWN, "127.0.0.1", 9000))
        self.assertEqual(len(self.table), 0)

    def test_added_contact_can_be_found(self):
        c = contact_in_bucket(5)
        self.table.add(c)
        self.assertIs(self.table.get(c.id), c)
        self.assertEqual(len(self.table), 1)

    def test_unknown_contact_is_none(self):
        self.assertIsNone(self.table.get(OWN ^ 12345))

    def test_contact_goes_into_the_bucket_for_its_xor_distance(self):
        c = contact_in_bucket(7)
        self.table.add(c)
        self.assertEqual(len(self.table.buckets[7]), 1)
        self.assertIs(self.table.buckets[7][0], c)

    def test_seen_again_moves_to_most_recent_and_resets_failures(self):
        c1, c2 = contact_in_bucket(5, 1), contact_in_bucket(5, 2)
        self.table.add(c1)
        self.table.add(c2)
        c1.fails = 1
        self.table.add(Contact(c1.id, "127.0.0.1", 9001))   # c1 answered again
        bucket = self.table.buckets[5]
        self.assertEqual([x.id for x in bucket], [c2.id, c1.id])
        self.assertEqual(c1.fails, 0)

    def test_bucket_holds_at_most_k_and_overflow_goes_to_cache(self):
        for n in range(K + 3):
            self.table.add(contact_in_bucket(20, n))
        self.assertEqual(len(self.table.buckets[20]), K)
        self.assertEqual(len(self.table.cache[20]), 3)

    def test_removing_a_contact_promotes_a_cached_one(self):
        contacts = [contact_in_bucket(20, n) for n in range(K + 1)]
        for c in contacts:
            self.table.add(c)
        self.assertEqual(len(self.table.cache[20]), 1)
        self.table.remove(contacts[0].id)
        self.assertIsNone(self.table.get(contacts[0].id))
        self.assertEqual(len(self.table.buckets[20]), K)
        self.assertIsNotNone(self.table.get(contacts[K].id))
        self.assertEqual(len(self.table.cache[20]), 0)

    def test_closest_returns_contacts_sorted_by_xor_distance(self):
        contacts = [contact_in_bucket(i) for i in (3, 9, 30, 60, 100)]
        for c in contacts:
            self.table.add(c)
        target = OWN ^ (1 << 3)
        expected = sorted(contacts, key=lambda c: c.id ^ target)[:3]
        got = self.table.closest(target, 3)
        self.assertEqual([c.id for c in got], [c.id for c in expected])

    def test_closest_can_exclude_contacts(self):
        contacts = [contact_in_bucket(i) for i in (3, 9, 30)]
        for c in contacts:
            self.table.add(c)
        got = self.table.closest(OWN, 10, exclude={contacts[0].id})
        self.assertNotIn(contacts[0].id, [c.id for c in got])
        self.assertEqual(len(got), 2)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.dht = DHT(OWN, 9000, b"test-secret")

    def test_stored_value_can_be_read(self):
        self.dht._local_put("k", "v", 60, 1.0)
        self.assertEqual(self.dht._local_get("k"), "v")

    def test_missing_key_is_none(self):
        self.assertIsNone(self.dht._local_get("nope"))

    def test_newer_version_overwrites_older(self):
        self.dht._local_put("k", "old", 60, 1.0)
        self.dht._local_put("k", "new", 60, 2.0)
        self.assertEqual(self.dht._local_get("k"), "new")

    def test_late_older_update_does_not_overwrite_newer(self):
        self.dht._local_put("k", "new", 60, 2.0)
        self.dht._local_put("k", "old", 60, 1.0)      # arrives late
        self.assertEqual(self.dht._local_get("k"), "new")

    def test_expired_value_is_hidden_and_cleaned_up(self):
        self.dht._local_put("k", "v", -1, 1.0)         # already expired
        self.assertIsNone(self.dht._local_get("k"))
        self.dht.expire()
        self.assertNotIn("k", self.dht.storage)


if __name__ == "__main__":
    unittest.main(verbosity=2)