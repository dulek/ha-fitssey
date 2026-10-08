# Fitssey for Home Assistant

A read-only Home Assistant integration that shows Fitssey classes as room calendars. It does not control HVAC or other devices; use Home Assistant automations for that.

## What it provides

- One `calendar` entity for each room returned by Fitssey, even when the room has no upcoming classes.
- Individual class events with the class name, room, start and end time. Cancelled classes are omitted.
- A five-minute poll of the next two weeks for calendar state and automation triggers. Calendar views outside that window are fetched on demand and cached briefly.
- Support for multiple studios, newly created rooms, and API-key rotation through Home Assistant.

The integration reads Fitssey API v4 `GET /location/all` and `GET /schedule`. It does not request client lists, attendance records, or write to Fitssey. Hidden classes are included if Fitssey returns them and they have a room; a hidden class may still reserve a physical room.

API reference: [Fitssey API v4](https://app.fitssey.com/docs/api).

## Installation

Once this repository is hosted on GitHub, add it to HACS as a **custom repository** of type **Integration**, download Fitssey, and restart Home Assistant. For a local installation, copy `custom_components/fitssey` into your Home Assistant configuration's `custom_components` directory and restart.

Then go to **Settings → Devices & services → Add integration → Fitssey**. Enter the studio identifier shown in Fitssey Studio and a dedicated API key from **Fitssey Studio → Integrations → API Keys**. The identifier is treated as text and does not need a UUID format. The integration checks both required endpoints before saving the entry. Choose a different key for each Home Assistant installation.

The repository is prepared for HACS; it cannot be installed through HACS until it is pushed to a GitHub repository. The documentation and issue-tracker links in `manifest.json` target the intended `dulek/ha-fitssey` repository and should be updated if published elsewhere.

## Automations

Each room is a standard Home Assistant calendar. You can use a calendar start trigger with a negative offset to prepare a room before class. For rules involving several adjacent classes, cancellation checks, or a dashboard-adjustable lead time, use `calendar.get_events` in an automation and evaluate the returned events. Keep all device control and preparation rules in Home Assistant.

Home Assistant checks calendar triggers about every 15 minutes. A class added at very short notice may be missed by a start trigger; consider a periodic reconciliation automation for important equipment. The integration itself refreshes Fitssey every five minutes, subject to the service being available.

## Credentials and privacy

The API key is entered in a masked field and stored in Home Assistant's config entry storage. It is never written to this repository, used in a URL, included in calendar events, or logged by this integration. Home Assistant's config-entry storage and backups are **not encrypted by this integration**: protect access to the HA host and its backups. Revoke a compromised key in Fitssey, then use **Reconfigure** on the integration to enter a replacement.

## Development

The repository follows HACS's `custom_components/fitssey` structure. Run `python -m compileall custom_components/fitssey` and `pytest tests` for local checks. Live API behavior requires a Fitssey studio identifier and API key and has not been verified against a real studio yet.
