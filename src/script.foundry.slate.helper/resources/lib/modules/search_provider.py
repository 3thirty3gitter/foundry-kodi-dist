# -*- coding: utf-8 -*-
"""
Foundry Helper - search provider picker.
Only installed search-capable video add-ons are offered. If none are
installed, the user is offered a redirect into the repository installer
(show_repos - the 'all repos' view).
"""

import xbmc
import xbmcgui

from modules.repo_installer import show_repos

# Slots must match the skin's CurrentSearchProviderToggleVar mapping.
PROVIDERS = [
    {"slot": "0", "id": "plugin.video.fen", "label": "FEN"},
    {"slot": "1", "id": "plugin.video.fenlight", "label": "FEN Light"},
    {"slot": "2", "id": "plugin.video.umbrella", "label": "Umbrella"},
    {"slot": "3", "id": "plugin.video.pov", "label": "POV"},
    {"slot": "4", "id": "plugin.video.seren", "label": "Seren"},
]


def _is_installed(addon_id):
    return bool(xbmc.getCondVisibility(
        "System.HasAddon(%s) + System.AddonIsEnabled(%s)" % (addon_id, addon_id)
    ))


def choose_search_provider():
    installed = [p for p in PROVIDERS if _is_installed(p["id"])]

    if not installed:
        if xbmcgui.Dialog().yesno(
            "Foundry Search",
            "No search add-ons installed.[CR][CR]Open the repository "
            "installer to add some?",
            nolabel="Not now",
            yeslabel="Install add-ons",
        ):
            show_repos()
        return

    current = xbmc.getInfoLabel("Skin.String(current_search_provider)")
    labels = [p["label"] for p in installed]
    preselect = next(
        (i for i, p in enumerate(installed) if p["slot"] == current), -1
    )
    idx = xbmcgui.Dialog().select(
        "Choose search provider", labels, preselect=preselect
    )
    if idx is not None and idx >= 0:
        xbmc.executebuiltin(
            "Skin.SetString(current_search_provider,%s)"
            % installed[idx]["slot"]
        )
