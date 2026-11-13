# -*- coding: utf-8 -*-
import xbmc
from xbmcgui import Window
from xbmc import sleep, getInfoLabel
from xbmcvfs import translatePath
from xbmcaddon import Addon
import json
import hashlib
import sqlite3
import os

# from modules.logger import logger

window = Window(10000)

PROFILE_PATH = os.path.join(
    translatePath("special://profile/addon_data/script.foundry.slate.helper"),
    "current_profile.json",
)


VERSIONS_PATH = os.path.join(os.path.dirname(PROFILE_PATH), "generated_skin_versions.json")


def saved_versions():
    try:
        with open(VERSIONS_PATH, "r", encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def generated_fingerprints():
    result = {}
    for kind in ("widget", "main_menu"):
        for category in ("movies", "tvshows", "custom1", "custom2", "custom3"):
            name = "script-nimbus-%s_%s.xml" % (kind, category)
            try:
                with open(translatePath("special://home/addons/skin.foundry.slate/xml/" + name), "rb") as stream:
                    result[name] = hashlib.sha256(stream.read()).hexdigest()
            except OSError:
                result[name] = None
    return result


def save_version(skin_id, version):
    versions = saved_versions()
    versions[skin_id] = {"version": version, "files": generated_fingerprints()}
    write_versions(versions)


def write_versions(versions):
    os.makedirs(os.path.dirname(VERSIONS_PATH), exist_ok=True)
    temporary = VERSIONS_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(versions, stream)
    os.replace(temporary, VERSIONS_PATH)


def record_generated_path(xml_file):
    # An intentional settings edit changes one include. Refresh only that
    # fingerprint, so unrelated missing/replaced includes still trigger recovery.
    skin_id = "skin.foundry.slate"
    versions = saved_versions()
    receipt = versions.get(skin_id)
    installed = Addon(id=skin_id).getAddonInfo("version")
    if not isinstance(receipt, dict) or receipt.get("version") != installed:
        return
    files = receipt.get("files")
    name = os.path.basename(translatePath(xml_file))
    if not isinstance(files, dict) or name not in files:
        return
    with open(translatePath(xml_file), "rb") as stream:
        files[name] = hashlib.sha256(stream.read()).hexdigest()
    write_versions(versions)


def check_for_update(skin_id):
    # SQLite provides a cross-invoker/process lock on all supported Kodi targets;
    # unlike a lock-file flag it releases automatically on crash or shutdown.
    lock_path = translatePath("special://masterprofile/addon_data/script.foundry.slate.helper/generated_paths_lock.db")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock = sqlite3.connect(lock_path, timeout=0)
    try:
        lock.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as error:
        lock.close()
        if "locked" in str(error).lower():
            return
        raise
    busy = "%s.rebuilding_paths" % skin_id
    try:
        # Window properties disappear at process restart. Fingerprints also
        # detect same-version reinstall or a different profile's shared XML.
        installed_version = Addon(id=skin_id).getAddonInfo("version")
        receipt = saved_versions().get(skin_id)
        if isinstance(receipt, dict) and receipt.get("version") == installed_version and receipt.get("files") == generated_fingerprints():
            set_installed_version(skin_id, installed_version)
            return
        window.setProperty(busy, "true")
        from modules.cpath_maker import remake_all_cpaths, reload_generated_paths
        remake_all_cpaths(silent=True, reload=False)
        # Mark only a complete successful rebuild, and before ReloadSkin can
        # re-enter Home. A failure leaves the old receipt so the next load retries.
        save_version(skin_id, installed_version)
        set_installed_version(skin_id, installed_version)
        reload_generated_paths()
    finally:
        window.clearProperty(busy)
        lock.close()


def set_installed_version(skin_id, installed_version):
    window.setProperty("%s.installed_version" % skin_id, installed_version)


def set_current_profile(skin_id, current_profile):
    dir_path = os.path.dirname(PROFILE_PATH)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    with open(PROFILE_PATH, "w") as f:
        json.dump(current_profile, f)
    window.setProperty("%s.current_profile" % skin_id, current_profile)

def get_profile_count():
    json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Profiles.GetProfiles", "id": 1}')
    json_response = json.loads(json_query)
    if 'result' in json_response and 'profiles' in json_response['result']:
        return len(json_response['result']['profiles'])
    return 0

def check_for_profile_change(skin_id):
    if get_profile_count() <= 1:
        return
    # Generated includes live in the shared skin directory. Each profile's own
    # fingerprints detect another profile's layout, using the same guarded
    # rebuild path rather than launching a second independent batch.
    check_for_update(skin_id)
    set_current_profile(skin_id, getInfoLabel("System.ProfileName"))
