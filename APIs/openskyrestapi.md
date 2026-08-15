# OpenSky Network REST API

> Reference: OpenSky Network API v1.4.0 — <https://openskynetwork.github.io/opensky-api/rest.html>

The root URL of the REST API is:

```
https://opensky-network.org/api
```

There are several functions available to retrieve state vectors, flights and tracks for the whole network, a particular sensor, or a particular aircraft. Functions that retrieve state vectors of sensors other than your own are rate limited (see [Limitations](#limitations) and [API Credits](#api-credits)).

---

## Authentication

OpenSky exclusively supports the **OAuth2 client credentials flow**. Basic authentication with username and password is no longer accepted.

To get started:

1. Log in to your OpenSky account and visit the **Account** page.
2. Create a new API client and retrieve your `client_id` and `client_secret`.
3. Exchange these for an access token, then pass it as a **Bearer** token on every request.

```bash
export CLIENT_ID=your_client_id
export CLIENT_SECRET=your_client_secret

export TOKEN=$(curl -X POST "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=$CLIENT_ID" \
  -d "client_secret=$CLIENT_SECRET" | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" https://opensky-network.org/api/states/all | jq .
```

Tokens expire after **30 minutes**. A `401 Unauthorized` response means the token has expired — request a new one and retry.

### Python Token Manager Example

For scripts making multiple calls, use this `TokenManager` class to handle token refresh automatically:

```python
import requests
from datetime import datetime, timedelta

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"

# How many seconds before expiry to proactively refresh the token.
TOKEN_REFRESH_MARGIN = 30


class TokenManager:
    def __init__(self):
        self.token = None
        self.expires_at = None

    def get_token(self):
        """Return a valid access token, refreshing automatically if needed."""
        if self.token and self.expires_at and datetime.now() < self.expires_at:
            return self.token
        return self._refresh()

    def _refresh(self):
        """Fetch a new access token from the OpenSky authentication server."""
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        r.raise_for_status()

        data = r.json()
        self.token = data["access_token"]
        expires_in = data.get("expires_in", 1800)
        self.expires_at = datetime.now() + timedelta(seconds=expires_in - TOKEN_REFRESH_MARGIN)
        return self.token

    def headers(self):
        """Return request headers with a valid Bearer token."""
        return {"Authorization": f"Bearer {self.get_token()}"}


# Create a single shared instance for your script.
tokens = TokenManager()

# Use it for any API call - the token is refreshed automatically.
response = requests.get(
    "https://opensky-network.org/api/states/all",
    headers=tokens.headers(),
)
print(response.json())
```

- `get_token()` only fetches a new token when the current one is about to expire.
- `headers()` can be passed directly to any `requests` call.
- Create one `TokenManager` instance and reuse it for all requests in your script.

---

## All State Vectors

Retrieve any state vector of the OpenSky network. **Rate limits apply** for this call (see [Limitations](#limitations)). For calls without rate limitation, see [Own State Vectors](#own-state-vectors).

### Operation

```
GET /states/all
```

### Request

You can optionally request state vectors for particular airplanes or times using the following request parameters:

| Property | Type | Description |
| --- | --- | --- |
| `time` | integer | The time in seconds since epoch (Unix timestamp) to retrieve states for. Current time is used if omitted. |
| `icao24` | string | One or more ICAO24 transponder addresses as a hex string (e.g. `abc9f3`). Append the property once for each address to filter multiple. If omitted, state vectors of all aircraft are returned. |

It is also possible to query a certain area defined by a bounding box of WGS84 coordinates. Add **all** of the following parameters:

| Property | Type | Description |
| --- | --- | --- |
| `lamin` | float | Lower bound for the latitude in decimal degrees |
| `lomin` | float | Lower bound for the longitude in decimal degrees |
| `lamax` | float | Upper bound for the latitude in decimal degrees |
| `lomax` | float | Upper bound for the longitude in decimal degrees |

You can request the category of aircraft by adding:

| Property | Type | Description |
| --- | --- | --- |
| `extended` | integer | Set to `1` if required |

**Example — query with time and aircraft:**

```
https://opensky-network.org/api/states/all?time=1458564121&icao24=3c6444
```

**Example — bounding box covering Switzerland:**

```
https://opensky-network.org/api/states/all?lamin=45.8389&lomin=5.9962&lamax=47.8229&lomax=10.5226
```

### Response

The response is a JSON object with the following properties:

| Property | Type | Description |
| --- | --- | --- |
| `time` | integer | The time which the state vectors in this response are associated with. All vectors represent the state of a vehicle within the interval `[time − 1, time]`. |
| `states` | array | The state vectors. |

The `states` property is a two-dimensional array. Each row is a state vector with the following fields:

| Index | Property | Type | Description |
| --- | --- | --- | --- |
| 0 | `icao24` | string | Unique ICAO 24-bit address of the transponder in hex string representation. |
| 1 | `callsign` | string | Callsign of the vehicle (8 chars). Can be null if no callsign has been received. |
| 2 | `origin_country` | string | Country name inferred from the ICAO 24-bit address. |
| 3 | `time_position` | int | Unix timestamp (seconds) for the last position update. Can be null if no position report was received by OpenSky within the past 15s. |
| 4 | `last_contact` | int | Unix timestamp (seconds) for the last update in general. Updated for any new, valid message received from the transponder. |
| 5 | `longitude` | float | WGS-84 longitude in decimal degrees. Can be null. |
| 6 | `latitude` | float | WGS-84 latitude in decimal degrees. Can be null. |
| 7 | `baro_altitude` | float | Barometric altitude in meters. Can be null. |
| 8 | `on_ground` | boolean | Indicates if the position was retrieved from a surface position report. |
| 9 | `velocity` | float | Velocity over ground in m/s. Can be null. |
| 10 | `true_track` | float | True track in decimal degrees clockwise from north (north = 0°). Can be null. |
| 11 | `vertical_rate` | float | Vertical rate in m/s. Positive = climbing, negative = descending. Can be null. |
| 12 | `sensors` | int[] | IDs of the receivers which contributed to this state vector. Null if no sensor filtering was used in the request. |
| 13 | `geo_altitude` | float | Geometric altitude in meters. Can be null. |
| 14 | `squawk` | string | The transponder code (Squawk). Can be null. |
| 15 | `spi` | boolean | Whether flight status indicates special purpose indicator. |
| 16 | `position_source` | int | Origin of this state's position (see below). |
| 17 | `category` | int | Aircraft category (see below). |

**`position_source` values:**

| Value | Meaning |
| --- | --- |
| 0 | ADS-B |
| 1 | ASTERIX |
| 2 | MLAT |
| 3 | FLARM |

**`category` values:**

| Value | Meaning |
| --- | --- |
| 0 | No information at all |
| 1 | No ADS-B Emitter Category Information |
| 2 | Light (< 15500 lbs) |
| 3 | Small (15500 to 75000 lbs) |
| 4 | Large (75000 to 300000 lbs) |
| 5 | High Vortex Large (aircraft such as B-757) |
| 6 | Heavy (> 300000 lbs) |
| 7 | High Performance (> 5g acceleration and 400 kts) |
| 8 | Rotorcraft |
| 9 | Glider / sailplane |
| 10 | Lighter-than-air |
| 11 | Parachutist / Skydiver |
| 12 | Ultralight / hang-glider / paraglider |
| 13 | Reserved |
| 14 | Unmanned Aerial Vehicle |
| 15 | Space / Trans-atmospheric vehicle |
| 16 | Surface Vehicle – Emergency Vehicle |
| 17 | Surface Vehicle – Service Vehicle |
| 18 | Point Obstacle (includes tethered balloons) |
| 19 | Cluster Obstacle |
| 20 | Line Obstacle |

### Examples

Retrieve all states as an anonymous user:

```bash
curl -s "https://opensky-network.org/api/states/all" | python -m json.tool
```

Retrieve all states as an authenticated OpenSky user:

```bash
curl -H "Authorization: Bearer $TOKEN" -s "https://opensky-network.org/api/states/all" | python -m json.tool
```

Retrieve states of two particular airplanes:

```bash
curl -s "https://opensky-network.org/api/states/all?icao24=3c6444&icao24=3e1bf9" | python -m json.tool
```

---

## Limitations

**Anonymous users** (unauthenticated, bucketed by IP):

- Only the most recent state vectors are available — the `time` parameter is ignored.
- Time resolution is 10 seconds: `now − (now mod 10)`.

**Authenticated users:**

- State vectors up to **1 hour** in the past. Requests with `t < now − 3600` return `400 Bad Request`.
- Time resolution is 5 seconds: `t − (t mod 5)`.

> **Note:** You can retrieve state vectors from your own receivers without any credit cost or time restriction. See [Own State Vectors](#own-state-vectors).

---

## API Credits

All endpoints consume credits except `/states/own`. Credits are tracked in **three independent buckets** — one each for `/states/*`, `/tracks/*`, and `/flights/*`. Spending credits on one endpoint has no effect on the others.

**Credit quotas by tier** (per endpoint — states, tracks, and flights each have their own independent quota):

| Tier | Credits | Refill |
| --- | --- | --- |
| Anonymous | 400 | Daily |
| Standard user | 4,000 | Daily |
| Active feeder (≥30% uptime/month) | 8,000 | Daily |
| Licensed user | 14,400 | Hourly |

> **Note:** Active feeder status is recalculated every 2 hours. Tier upgrades take effect after ~50 requests. To confirm you are receiving the 8,000-credit allowance, check that `X-Rate-Limit-Remaining` exceeds 4,000 at the start of a day.

**Credit cost — `/states/all`** (bounding box area in sq° = latitude range × longitude range):

| Bounding box area | Credits |
| --- | --- |
| ≤ 25 sq° or serial-only query | 1 |
| 25 – 100 sq° | 2 |
| 100 – 400 sq° | 3 |
| > 400 sq° or global | 4 |

**Credit cost — `/flights/*` and `/tracks/*`** (by day partitions — calendar day boundaries crossed by the time range):

| Partitions | Credits |
| --- | --- |
| Live / < 24 h | 4 |
| 1 – 2 | 30 |
| 3 – 10 | 60 × N |
| 11 – 15 | 120 × N |
| 16 – 20 | 240 × N |
| 21 – 25 | 480 × N |
| > 25 | 960 × N |

When credits are available, `X-Rate-Limit-Remaining` shows your remaining balance. When exhausted, the API returns `429 Too Many Requests` and `X-Rate-Limit-Retry-After-Seconds` indicates how many seconds to wait.

---

## Own State Vectors

Retrieve state vectors for your own sensors **without rate limitations**. Authentication is **required**, otherwise you get `403 - Forbidden`.

### Operation

```
GET /states/own
```

### Request

Pass one of the following optional properties as request parameters:

| Property | Type | Description |
| --- | --- | --- |
| `time` | integer | The time in seconds since epoch (Unix timestamp) to retrieve states for. Current time is used if omitted. |
| `icao24` | string | One or more ICAO24 transponder addresses as a hex string (e.g. `abc9f3`). Append once for each address. If omitted, all aircraft are returned. |
| `serials` | integer | Retrieve only states of a subset of your receivers. Pass several times to filter more than one receiver. The API returns all states of aircraft visible to at least one given receiver. |

### Response

Same structure as [All State Vectors](#all-state-vectors): a JSON object with `time` and `states`, where `states` is a two-dimensional array with the same 18 fields (indices 0–17) described above.

### Examples

Retrieve states for all sensors that belong to you:

```bash
curl -H "Authorization: Bearer $TOKEN" -s "https://opensky-network.org/api/states/own" | python -m json.tool
```

Retrieve states as seen by a specific sensor with serial `123456`:

```bash
curl -H "Authorization: Bearer $TOKEN" -s "https://opensky-network.org/api/states/own?serials=123456" | python -m json.tool
```

Retrieve states for several receivers:

```bash
curl -H "Authorization: Bearer $TOKEN" -s "https://opensky-network.org/api/states/own?serials=123456&serials=98765" | python -m json.tool
```

---

## Flights in Time Interval

Retrieve flights for a certain time interval `[begin, end]`. If no flights are found, HTTP `404 - Not found` is returned with an empty response body.

### Operation

```
GET /flights/all
```

### Request

| Property | Type | Description |
| --- | --- | --- |
| `begin` | integer | Start of time interval as Unix time (seconds since epoch) |
| `end` | integer | End of time interval as Unix time (seconds since epoch) |

> The given time interval **must not be larger than two hours**.

### Response

The response is a JSON array of flights, where each flight is an object.

### Examples

Get flights from 12pm to 1pm on Jan 29 2018:

```bash
curl -H "Authorization: Bearer $TOKEN" -s "https://opensky-network.org/api/flights/all?begin=1517227200&end=1517230800" | python -m json.tool
```

---

## Flights by Aircraft

Retrieve flights for a particular aircraft within a time interval. Resulting flights departed and arrived within `[begin, end]`. If none are found, HTTP `404 - Not found` is returned with an empty body.

> **Note:** Flights are updated by a batch process at night — only flights from the previous day or earlier are available using this endpoint.

### Operation

```
GET /flights/aircraft
```

### Request

| Property | Type | Description |
| --- | --- | --- |
| `icao24` | string | Unique ICAO 24-bit address of the transponder in hex string representation. All letters must be lower case. |
| `begin` | integer | Start of time interval as Unix time (seconds since epoch) |
| `end` | integer | End of time interval as Unix time (seconds since epoch) |

> The given time interval **must not be larger than 2 days**.

### Response

The response is a JSON array of flights, where each flight is an object.

### Examples

Get flights for D-AIZZ (`3c675a`) on Jan 29 2018:

```bash
curl -H "Authorization: Bearer $TOKEN" -s "https://opensky-network.org/api/flights/aircraft?icao24=3c675a&begin=1517184000&end=1517270400" | python -m json.tool
```

---

## Arrivals by Airport

Retrieve flights for a certain airport which arrived within `[begin, end]`. If none are found, HTTP `404 - Not found` is returned with an empty body.

> **Note:** Similar to flights, arrivals are updated by a batch process at night — only arrivals from the previous day or earlier are available.

### Operation

```
GET /flights/arrival
```

### Request

| Property | Type | Description |
| --- | --- | --- |
| `airport` | string | ICAO identifier for the airport |
| `begin` | integer | Start of time interval as Unix time (seconds since epoch) |
| `end` | integer | End of time interval as Unix time (seconds since epoch) |

> The given time interval **must not be larger than two days**.

### Response

The response is a JSON array of flights, where each flight is an object.

### Examples

Get all flights arriving at Frankfurt International Airport (EDDF) from 12pm to 1pm on Jan 29 2018:

```bash
curl -H "Authorization: Bearer $TOKEN" -s "https://opensky-network.org/api/flights/arrival?airport=EDDF&begin=1517227200&end=1517230800" | python -m json.tool
```

---

## Departures by Airport

Retrieve flights for a certain airport which departed within `[begin, end]`. If none are found, HTTP `404 - Not found` is returned with an empty body.

### Operation

```
GET /flights/departure
```

### Request

| Property | Type | Description |
| --- | --- | --- |
| `airport` | string | ICAO identifier for the airport (usually upper case) |
| `begin` | integer | Start of time interval as Unix time (seconds since epoch) |
| `end` | integer | End of time interval as Unix time (seconds since epoch) |

### Response

The response is a JSON array of flights, where each flight is an object.

### Examples

Get all flights departing from Frankfurt International Airport (EDDF) from 12pm to 1pm on Jan 29 2018:

```bash
curl -H "Authorization: Bearer $TOKEN" -s "https://opensky-network.org/api/flights/departure?airport=EDDF&begin=1517227200&end=1517230800" | python -m json.tool
```

---

## Track by Aircraft

> **Note:** The tracks endpoint is purely **experimental** and can be out of order at any time. For historical data, use the [Flights in Time Interval](#flights-in-time-interval) endpoint.

Retrieve the trajectory for a certain aircraft at a given time. The trajectory is a list of waypoints containing position, barometric altitude, true track, and an on-ground flag.

Unlike state vectors, trajectories do not contain all information about the flight, but show the aircraft's general movement pattern. Waypoints are selected among available state vectors given these rules:

- The first point is set immediately after the aircraft's expected departure, or after the network received the first position when the aircraft entered its reception range.
- The last point is set right before the aircraft's expected arrival, or when the aircraft left the network's reception range.
- There is a waypoint at least every 15 minutes when the aircraft is in-flight.
- A waypoint is added if the aircraft changes its track more than 2.5°.
- A waypoint is added if the aircraft changes altitude by more than 100m (~330ft).
- A waypoint is added if the on-ground state changes.

Tracks are strongly related to flights and are computed within the same processing step. It may be beneficial to first retrieve a list of flights, then use those timestamps to retrieve detailed track information.

### Operation

```
GET /tracks
```

### Request

| Property | Type | Description |
| --- | --- | --- |
| `icao24` | string | Unique ICAO 24-bit address of the transponder in hex string representation. All letters must be lower case. |
| `time` | integer | Unix time in seconds since epoch. Can be any time between start and end of a known flight. If `time = 0`, get the live track if there is any ongoing flight for the given aircraft. |

### Response

The response is a JSON object with the following properties:

| Property | Type | Description |
| --- | --- | --- |
| `icao24` | string | Unique ICAO 24-bit address of the transponder in lower case hex string representation. |
| `startTime` | integer | Time of the first waypoint in seconds since epoch (Unix time). |
| `endTime` | integer | Time of the last waypoint in seconds since epoch (Unix time). |
| `callsign` | string | Callsign (8 characters) that holds for the whole track. Can be null. |
| `path` | array | Waypoints of the trajectory (see below). |

Waypoints are represented as JSON arrays to save bandwidth. Each point contains:

| Index | Property | Type | Description |
| --- | --- | --- | --- |
| 0 | `time` | integer | Time the waypoint is associated with in seconds since epoch (Unix time). |
| 1 | `latitude` | float | WGS-84 latitude in decimal degrees. Can be null. |
| 2 | `longitude` | float | WGS-84 longitude in decimal degrees. Can be null. |
| 3 | `baro_altitude` | float | Barometric altitude in meters. Can be null. |
| 4 | `true_track` | float | True track in decimal degrees clockwise from north (north = 0°). Can be null. |
| 5 | `on_ground` | boolean | Indicates if the position was retrieved from a surface position report. |

### Limitations

It is **not possible** to access flight tracks from more than 30 days in the past.

### Examples

Get the live track for aircraft with transponder address `3c4b26` (D-ABYF):

```bash
curl -H "Authorization: Bearer $TOKEN" -s "https://opensky-network.org/api/tracks/all?icao24=3c4b26&time=0"
```

---

> **See also — Historical Data:** For historical data spanning more than one hour, use the **Trino / MinIO** interface instead of the REST API.
