# Real OSM road data for M3 local/CI

`Saigon.osm.pbf` is the unmodified public BBBike Saigon OpenStreetMap extract downloaded for M3 verification on 06/10/2026. It contains real road/map data, no customer information or configured company coordinates.

- Source: https://download.bbbike.org/osm/bbbike/Saigon/Saigon.osm.pbf
- SHA256: `305729efc04180b6a151ba3d61f6bb5c91b05ed044eed734b30f3625f806119b`
- Copyright: © OpenStreetMap contributors; extraction service BBBike.org.
- License: Open Database License (ODbL) 1.0, https://www.openstreetmap.org/copyright and https://opendatacommons.org/licenses/odbl/1-0/.

CI builds its own OSRM MLD graph from these bytes with the official v6.0.0 container. The public download timed out on the GitHub runner in run 37461848874; the versioned extract makes CI reproducible and keeps validation real. There is no route/matrix mock or crow-flight fallback.

The fixture covers Saigon only; operations outside the extract require a configured real dataset covering that region. Company/customer coordinates are not inferred from this file. Local preparation can still use the public download or the checksum-verified `--pbf` input. Dataset provenance/hash is recorded in the generated metadata; changed datasets invalidate unapproved optimization snapshots.
