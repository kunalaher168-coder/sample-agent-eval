No new public interfaces are required. The interfaces below already exist and must keep their signatures and documented behavior.

Type: Constant
Name: DEFAULT_TRANSFER_MINUTES
Location: transit/network.py
Signature: DEFAULT_TRANSFER_MINUTES = 4.0
Description: Time used for a transfer link that has no minutes value in the network file. The value stays 4.0.

Type: Function
Name: build_network
Location: transit/network.py
Signature: build_network(data: dict) -> Network
Description: Builds a Network from parsed network data. Every link can be travelled in both directions. A negative minutes value raises ValueError.

Type: Function
Name: load_network
Location: transit/network.py
Signature: load_network(path: str | Path) -> Network
Description: Reads a network JSON file and returns build_network() of its contents.

Type: Function
Name: plan
Location: transit/router.py
Signature: plan(network: Network, origin_station: str, destination_station: str) -> Route
Description: Returns the fastest route between two stations. Station names are case-insensitive. Raises UnknownStationError for an unknown station and NoRouteError when no route exists.

Type: Class
Name: Route
Location: transit/router.py
Signature: legs: tuple[Leg, ...]; total_minutes: float; transfers (property) -> int
Description: A planned trip. transfers counts the legs whose kind is "transfer".
