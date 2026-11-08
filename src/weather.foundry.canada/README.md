# Foundry Canada Weather

Private development version 0.1.0 for Kodi 21 Omega. Release licensing and native Kodi/Shield QA are separate gates. This add-on is not enabled or selected automatically.

## Setup and use

Install the provider, select it explicitly in Kodi Settings > Services > Weather, then configure one to three Canadian cities in its settings. Search is manual and accent-insensitive. Cancelling search leaves settings unchanged. Selecting a later slot first fills the next empty slot.

The Foundry Home Weather card offers the seven-day forecast, advisory headlines, next city, refresh and settings. The card shows six hourly entries and five day cards; the provider exposes up to 24 hourly and seven daily entries. Other selected weather providers retain their existing Home presentation. Regional Celsius/Fahrenheit and device-local time formatting are respected. Times are not converted to the selected city's time zone.

Missing observations are not represented as zero. Cached/delayed results are marked. Advisory headlines include official links and issue/expiry times, are not full CAP bulletins, and do not replace an emergency-warning service. An empty list is not an all-clear statement.

## Privacy and network behavior

No account, API key, GPS, IP geolocation, analytics or background service. The public location catalogue is searched locally; typed search terms are not submitted. A forecast request sends the selected public location ID to the weather service, which also sees the connection IP. Selected IDs/labels and a bounded response cache stay in the Kodi add-on profile. No location or response contents are logged.

Ordinary Kodi weather refresh is approximately 30 minutes. The client reuses forecasts for 15 minutes, keeps last-good offline data for up to six hours, uses conditional requests and retry backoff, and verifies HTTPS. Catalogue caching lasts seven days with a bounded offline fallback. The experimental upstream API can change; invalid or mismatched results fail safely.

## Development and release

Run from the distribution checkout: `python -m unittest discover -s tests -p "test_weather*.py" -v`.

There is no automatic provider-setting change or deployment. Public distribution requires the owner's release/licensing review and a request-volume plan. See SOURCE.md for data rights and source acknowledgement. Do not remove required acknowledgement or imply official endorsement.
