"""End-to-end demo / sanity anchor.

Ingests a small European OED portfolio, runs a synthetic Kyrill-like windstorm footprint
(peak gusts over NW Europe: Benelux / N. Germany), and shows:
  * per-location losses concentrating inside the storm swath,
  * Madrid (well south of the track) taking ~zero loss,
  * the marginal impact of binding a new account — the underwriting wedge.

The footprint here is synthetic (a smooth gust field), standing in for a real XWS /
Copernicus raster which loads via engine.perils.windstorm.GriddedFootprint.from_geotiff.

Run:  python scripts/demo_scenario.py
"""

from __future__ import annotations

import numpy as np

from data.ingest import ingest_oed_locations
from engine.perils import windstorm
from engine.scenario.core import Exposure, compute_scenario_loss, marginal_impact


# A synthetic gust footprint: a Gaussian ridge of high gusts sweeping W->E across NW Europe,
# centred near Cologne (51N, 7E), tapering to calm toward the south (Madrid) — Kyrill-like.
class SyntheticStorm:
    peril = windstorm.PERIL

    def __init__(self, peak_ms=48.0, centre=(51.0, 7.0), spread_deg=6.0):
        self.peak = peak_ms
        self.clat, self.clon = centre
        self.spread = spread_deg

    def sample(self, lons, lats):
        lons, lats = np.asarray(lons, float), np.asarray(lats, float)
        # Latitude falloff is sharper than longitude (storms are broad E-W, narrow N-S).
        d2 = ((lons - self.clon) / (self.spread * 2)) ** 2 + ((lats - self.clat) / self.spread) ** 2
        return self.peak * np.exp(-d2)


# A tiny OED portfolio across Europe (as it would arrive in a location file).
PORTFOLIO_ROWS = [
    {"LocNumber": "LON", "CountryCode": "GB", "Latitude": "51.51", "Longitude": "-0.13",
     "BuildingTIV": "5000000", "ContentsTIV": "1000000", "BITIV": "0", "LocDed": "50000"},
    {"LocNumber": "PAR", "CountryCode": "FR", "Latitude": "48.85", "Longitude": "2.35",
     "BuildingTIV": "4000000", "ContentsTIV": "800000", "BITIV": "0", "LocDed": "40000"},
    {"LocNumber": "CGN", "CountryCode": "DE", "Latitude": "50.94", "Longitude": "6.96",
     "BuildingTIV": "6000000", "ContentsTIV": "1500000", "BITIV": "0", "LocDed": "60000"},
    {"LocNumber": "AMS", "CountryCode": "NL", "Latitude": "52.37", "Longitude": "4.90",
     "BuildingTIV": "3500000", "ContentsTIV": "700000", "BITIV": "0", "LocDed": "35000"},
    {"LocNumber": "MUC", "CountryCode": "DE", "Latitude": "48.14", "Longitude": "11.58",
     "BuildingTIV": "4500000", "ContentsTIV": "900000", "BITIV": "0", "LocDed": "45000"},
    {"LocNumber": "MAD", "CountryCode": "ES", "Latitude": "40.42", "Longitude": "-3.70",
     "BuildingTIV": "5000000", "ContentsTIV": "1000000", "BITIV": "0", "LocDed": "50000"},
]


def main() -> None:
    locations, report = ingest_oed_locations(PORTFOLIO_ROWS)
    print("Ingestion:", report.summary())

    exposure = Exposure.from_locations(locations)
    storm = SyntheticStorm()
    vulns = windstorm.default_vulnerabilities()

    result = compute_scenario_loss(exposure, storm, vulns)

    print("\nScenario: synthetic Kyrill-like windstorm")
    print(f"{'Loc':>5} {'gust m/s':>9} {'TIV':>12} {'net loss':>14}")
    for loc_id, gust, tiv, net in zip(
        result.loc_ids, result.intensities, exposure.tivs, result.net_loss
    ):
        print(f"{loc_id:>5} {gust:9.1f} {tiv:12,.0f} {net:14,.0f}")
    print(f"{'':>5} {'':>9} {'PORTFOLIO':>12} {result.total_net:14,.0f}")

    # Underwriting wedge: what does binding a new Brussels risk add?
    new_account = Exposure.from_locations(
        ingest_oed_locations([{
            "LocNumber": "BRU", "CountryCode": "BE", "Latitude": "50.85", "Longitude": "4.35",
            "BuildingTIV": "8000000", "ContentsTIV": "2000000", "BITIV": "0", "LocDed": "80000",
        }])[0]
    )
    impact = marginal_impact(result, new_account, storm, vulns)
    print("\nUnderwriting what-if: bind BRU (Brussels, inside the swath)")
    print(f"  marginal net loss added: {impact['delta_net']:,.0f}")
    print(f"  portfolio net {impact['portfolio_net_before']:,.0f} "
          f"-> {impact['portfolio_net_after']:,.0f}")


if __name__ == "__main__":
    main()
