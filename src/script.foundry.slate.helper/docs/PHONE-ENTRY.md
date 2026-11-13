# Phone keyboard

Open a normal Kodi keyboard in Foundry and select **Phone / Cancel**. Scan the QR using a phone on the same trusted private Wi-Fi network. Enter ordinary text and select **Send to TV**. Review it on the TV and press the existing **OK** button. Sending replaces the field, including with empty text, but never submits the Kodi dialog. Use the remote keyboard normally at any time.

The keyboard starts full size. Phone slides the QR panel out and smoothly adjusts the keyboard; Cancel revokes the session and restores the full-size keyboard.

The button is excluded for Kodi hidden/password/PIN input and numeric dialogs. Custom add-on keyboards, IPv6-only/public/link-local addresses and remote internet access are unsupported. A guest network or client-isolation/firewall policy may block access; the feature does not change those settings. Use the TV keyboard if unavailable.

## Local address selection

On Android/Linux, the helper discovers active physical Wi-Fi/Ethernet IPv4 interfaces locally instead of blindly using Kodi's selected IP, which can belong to a VPN. A valid physical Kodi address wins; otherwise one physical LAN address or a unique lowest-metric physical default route is selected. Tunnel, loopback, down, point-to-point, public and link-local interfaces are excluded. Ambiguous or inaccessible physical discovery produces a TV status and keeps remote entry available. Platforms without Unix interface discovery retain Kodi's validated private IPv4 address. No discovery packets, routing changes, firewall changes or all-interface listeners are used.

This avoids advertising a tunnel address when a discoverable physical LAN exists; it cannot defeat VPN LAN-blocking, Wi-Fi client isolation, firewall rules or a phone on a different network. Android device restrictions and real Shield/phone reachability still require device verification.

## Privacy and boundaries

This is local HTTP, **not encrypted**. Use trusted Wi-Fi only. Do not enter passwords, API keys, payment details or other private information, even when another add-on presents an ordinary unmasked field. No cloud relay, analytics, external QR service, third-party assets or persistent web service is used.

Each explicit activation creates a random 256-bit bearer capability, binds one ephemeral port to Kodi's specific RFC1918 IPv4 address, and lasts at most two minutes or one accepted send. Closing the keyboard, cancelling, changing skin, shutdown or losing the owning dialog invalidates the session. HTTP parsing has a two-second absolute deadline. Host and Origin must match the exact IP and port; cross-origin requests, unsupported payloads, oversized data and invalid tokens are rejected. No CORS access is granted.

The token travels in the QR URL fragment, which the page removes from its address using replaceState, then in the authorization header. HTTP responses prohibit caching/referrers/framing. Typed text is held only during processing, is never deliberately written to a file or application log, and is cleared from the page after an attempted send. Browser/OS keyboards and Kodi's own logging/settings remain outside this feature's control.

Kodi needs a file-backed image: a temporary PNG containing the short-lived QR token is written to special://temp and removed on normal exit. A crash or failed removal can leave this expired QR artifact behind; it contains no entered text. Do not claim zero secret persistence. The token becomes useless when its server exits or session expires.

Kodi's public Input.SendText API targets the active keyboard and has no per-dialog generation parameter. The helper checks current ownership, keyboard visibility and hidden-input state immediately before calling it and never auto-confirms. XML load/unload invalidates ownership. This prevents ordinary stale submissions, but cannot make validation and Kodi's dispatch atomic across an exactly simultaneous close/reopen. Native interruption coverage and review-on-TV remain release requirements.

## Dependency and verification

QR encoding uses the unmodified qrcodegen 1.8.0 module from PyPI, bundled under modules/vendor with its embedded MIT license. PNG rendering uses the existing Kodi PIL dependency. No new add-on dependency or background-service hook is required.

Run from sibling foundry-kodi-dist: python -X utf8 -m unittest discover -s tests -p test_phone_entry.py -v. Run the full distribution source and extracted-package tests and native Kodi 21+ keyboard checks before release. A real phone scan on the affected device/network is not established by loopback HTTP or container tests.
