import unittest
from pathlib import Path

from transit import NoRouteError, UnknownStationError, build_network, load_network, plan

DATA = Path(__file__).resolve().parent.parent / "data" / "network.json"


def tiny_network(transfer_minutes=2):
    return build_network({
        "stops": [
            {"id": "a_red", "station": "A", "line": "Red"},
            {"id": "b_red", "station": "B", "line": "Red"},
            {"id": "b_blue", "station": "B", "line": "Blue"},
            {"id": "c_blue", "station": "C", "line": "Blue"},
            {"id": "d_blue", "station": "D", "line": "Blue"},
        ],
        "links": [
            {"from": "a_red", "to": "b_red", "kind": "ride", "minutes": 3},
            {"from": "b_red", "to": "b_blue", "kind": "transfer", "minutes": transfer_minutes},
            {"from": "b_blue", "to": "c_blue", "kind": "ride", "minutes": 5},
        ],
    })


class SampleNetworkTests(unittest.TestCase):
    def setUp(self):
        self.network = load_network(DATA)

    def test_loads_all_stops(self):
        self.assertEqual(len(self.network.stops), 10)

    def test_single_line_trip(self):
        route = plan(self.network, "Harbor", "Central")
        self.assertEqual(route.total_minutes, 9)
        self.assertEqual(route.transfers, 0)

    def test_station_names_are_case_insensitive(self):
        route = plan(self.network, "harbor", "MARKET")
        self.assertEqual(route.total_minutes, 5)

    def test_same_station_is_an_empty_route(self):
        route = plan(self.network, "Museum", "Museum")
        self.assertEqual(route.legs, ())
        self.assertEqual(route.total_minutes, 0)


class RouterTests(unittest.TestCase):
    def test_route_with_timed_transfer(self):
        route = plan(tiny_network(transfer_minutes=2), "A", "C")
        self.assertEqual(route.total_minutes, 10)
        self.assertEqual(route.transfers, 1)

    def test_unknown_station(self):
        with self.assertRaises(UnknownStationError):
            plan(tiny_network(), "A", "Nowhere")

    def test_unreachable_station(self):
        with self.assertRaises(NoRouteError):
            plan(tiny_network(), "A", "D")

    def test_negative_minutes_rejected(self):
        with self.assertRaises(ValueError):
            tiny_network(transfer_minutes=-1)


if __name__ == "__main__":
    unittest.main()
