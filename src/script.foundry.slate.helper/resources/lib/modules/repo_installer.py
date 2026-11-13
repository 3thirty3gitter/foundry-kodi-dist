# -*- coding: utf-8 -*-
"""
Foundry Helper - repository installer.
Installs Kodi add-on repositories from their official ZIP URLs.
Carried over from the Foundry project-1 wizard repo list.

Patterns proven on Android TV (see brain memory learnings 2026-08):
- Downloads use Kodi's native network stack (xbmcvfs.copy), never urllib
- Zip install = extractall() into special://home/addons + UpdateLocalAddons()
  (the Kodi 21.3 InstallFromZip builtin ignores its path parameter)
"""

import json
import os
import zipfile
import uuid
import stat
import xml.etree.ElementTree as ET
import shutil
import xbmc
import xbmcgui
import xbmcvfs

ADDONS_DIR = xbmcvfs.translatePath("special://home/addons")
CACHE_DIR = os.path.join(
    xbmcvfs.translatePath("special://profile/addon_data/script.foundry.slate.helper"),
    "repo_cache",
)

REPOS = [
    {
        "name": "Rector Stuff Repository",
        "zip_url": "https://github.com/rmrector/repository.rector.stuff/raw/python2/latest/repository.rector.stuff-latest.zip",
        "addon_id": "repository.rector.stuff",
        "bundled": "repository.rector.stuff.zip",
        "provides": "Artwork Dump",
    },
    {
        "name": "The Crew Repository",
        "zip_url": "https://team-crew.github.io/repository.thecrew-0.3.8.zip",
        "addon_id": "repository.thecrew",
        "bundled": "repository.thecrew.zip",
        "provides": "The Crew",
    },
    {
        "name": "Umbrella Repository",
        "zip_url": "https://umbrellaplug.github.io/repository.umbrella-2.2.6.zip",
        "addon_id": "repository.umbrella",
        "bundled": "repository.umbrella.zip",
        "provides": "Umbrella",
    },
    {
        "name": "Seren Repository (NixGates)",
        "zip_url": "https://nixgates.github.io/packages/repository.nixgates-2.2.0.zip",
        "addon_id": "repository.nixgates",
        "bundled": "repository.nixgates.zip",
        "provides": "Seren",
    },
    {
        "name": "Gaia Repository",
        "zip_url": "https://repo.gaiakodi.com/repository.gaia.core.zip",
        "addon_id": "repository.gaia.core",
        "bundled": "repository.gaia.core.zip",
        "provides": "Gaia",
    },
    {
        "name": "Jacktook Repository",
        "zip_url": "https://sam-max.github.io/repository.jacktook/repository.jacktook-0.0.5.zip",
        "addon_id": "repository.jacktook",
        "bundled": "repository.jacktook.zip",
        "provides": "Jacktook",
    },
    {
        "name": "Slyguy Repository",
        "zip_url": "https://raw.githubusercontent.com/matthuisman/slyguy.addons/master/repository.slyguy.zip",
        "addon_id": "repository.slyguy",
        "bundled": "repository.slyguy.zip",
        "provides": "YouTube, IPTV Merge",
    },
    {
        "name": "Marcelveldt Beta Repository",
        "zip_url": "https://raw.githubusercontent.com/kodi-community-addons/repository.marcelveldt/master/repository.marcelveldt-1.0.3.zip",
        "addon_id": "repository.marcelveldt",
        "bundled": "repository.marcelveldt.zip",
        "provides": "Metadata Utils, Skin Helper Service",
    },
    {
        "name": "Jurialmunkey Alpha Repository",
        "zip_url": "https://raw.githubusercontent.com/jurialmunkey/repository.jurialmunkey/master/repository.jurialmunkey-3.4.zip",
        "addon_id": "repository.jurialmunkey",
        "bundled": "repository.jurialmunkey.zip",
        "provides": "Jurialmunkey add-ons",
    },
    {
        "name": "Gade Repository",
        "zip_url": "https://raw.githubusercontent.com/gade01/repository.gade/master/nexus/repository.gade/repository.gade-2.2.0.zip",
        "addon_id": "repository.gade",
        "bundled": "repository.gade.zip",
        "provides": "Gade add-ons",
    },
    {
        "name": "Bossanova808 Repository",
        "zip_url": "https://raw.githubusercontent.com/bossanova808/repository.bossanova808/main/repository-downloads/repository.bossanova808/repository.bossanova808-0.2.7.zip",
        "addon_id": "repository.bossanova808",
        "bundled": "repository.bossanova808.zip",
        "provides": "Bossanova808 add-ons",
    },
    {
        "name": "CocoScrapers Repository",
        "zip_url": "https://cocojoe2411.github.io/repository.cocoscrapers-1.0.1.zip",
        "addon_id": "repository.cocoscrapers",
        "bundled": "repository.cocoscrapers.zip",
        "provides": "CocoScrapers Module",
    },
]


def _has_addon(addon_id):
    try:
        result = json.loads(xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "method": "Addons.GetAddonDetails",
            "params": {"addonid": addon_id, "properties": ["enabled"]}, "id": 1
        })))
        return result.get("result", {}).get("addon", {}).get("addonid") == addon_id
    except Exception:
        return False


def _download_repo_zip(repo):
    if not xbmcvfs.exists(os.path.dirname(CACHE_DIR)):
        xbmcvfs.mkdirs(os.path.dirname(CACHE_DIR))
    xbmcvfs.mkdirs(CACHE_DIR)
    # Unique-per-run target prevents stale cached zips being reused
    target = os.path.join(CACHE_DIR, repo["addon_id"] + "-" + uuid.uuid4().hex + ".zip")
    ok = xbmcvfs.copy(repo["zip_url"], target)
    if not ok or not xbmcvfs.exists(target):
        return None
    return target


def _extract_to_addons(zip_path, addon_id):
    with zipfile.ZipFile(zip_path) as zf:
        roots = set()
        for entry in zf.infolist():
            parts = entry.filename.replace("\\", "/").split("/")
            if (not parts[0] or ":" in parts[0] or ".." in parts or
                    stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError("Repository ZIP contains an unsafe path")
            roots.add(parts[0])
        if len(roots) != 1:
            raise ValueError("Repository ZIP must contain one add-on folder")
        root = roots.pop()
        manifest = ET.fromstring(zf.read(root + "/addon.xml"))
        if manifest.get("id") != addon_id:
            raise ValueError("Repository ZIP addon ID does not match")
        for entry in zf.infolist():
            if entry.is_dir():
                continue
            relative = entry.filename.replace("\\", "/").split("/")[1:]
            target = os.path.join(ADDONS_DIR, addon_id, *relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(entry) as source, open(target, "wb") as destination:
                shutil.copyfileobj(source, destination)
    return True


def install_repo(repo):
    zip_path = _download_repo_zip(repo)
    if not zip_path:
        return False
    try:
        _extract_to_addons(zip_path, repo["addon_id"])
    except Exception as e:
        xbmc.log("[Foundry Helper] Repo extract failed %s: %s" % (repo["name"], str(e)), level=xbmc.LOGERROR)
        return False
    finally:
        try:
            xbmcvfs.delete(zip_path)
        except Exception:
            pass
    return True


BUNDLED_REPOS_DIR = "special://skin/extras/repos"


def _install_from_bundled(repo):
    """Install a repo from the zip bundled inside the skin package (offline)."""
    bundled = xbmcvfs.translatePath(
        BUNDLED_REPOS_DIR + "/" + repo["bundled"]
    )
    if not xbmcvfs.exists(BUNDLED_REPOS_DIR + "/" + repo["bundled"]):
        return False
    try:
        _extract_to_addons(bundled, repo["addon_id"])
        return True
    except Exception as e:
        xbmc.log(
            "[Foundry Helper] Bundled repo extract failed %s: %s"
            % (repo["name"], str(e)),
            level=xbmc.LOGERROR,
        )
        return False


def ensure_repos():
    """Install any missing Foundry repos. Bundled zips first (offline),
    source URLs as fallback. Idempotent no-op when all present. Runs from
    the skin home onload."""
    window = xbmcgui.Window(10000)
    if window.getProperty("foundry.slate.repos.installing") == "true":
        return False
    window.setProperty("foundry.slate.repos.installing", "true")
    installed, failed = [], []
    monitor = xbmc.Monitor()
    try:
        for repo in REPOS:
            if monitor.abortRequested():
                return False
            if _has_addon(repo["addon_id"]):
                continue
            if _install_from_bundled(repo) or install_repo(repo):
                installed.append(repo["addon_id"])
            else:
                failed.append(repo["name"])
        failed.extend(_register_repos(installed))
        if installed:
            message = ("Some repositories could not be prepared. Check the Kodi log."
                       if failed else "Repositories ready. Choose add-ons in Install from repository.")
            xbmcgui.Dialog().notification("Foundry", message, xbmcgui.NOTIFICATION_INFO, 5000)
        if failed:
            xbmc.log("[Foundry Helper] Repositories not ready: " + ", ".join(failed), xbmc.LOGERROR)
        return bool(installed)
    finally:
        window.clearProperty("foundry.slate.repos.installing")


def _register_repos(addon_ids):
    """Register and enable only repositories installed during this operation."""
    if not addon_ids:
        return []
    xbmc.executebuiltin("UpdateLocalAddons")
    pending = set(addon_ids)
    monitor = xbmc.Monitor()
    for _ in range(80):
        for addon_id in list(pending):
            if not _has_addon(addon_id):
                continue
            response = json.loads(xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled",
                "params": {"addonid": addon_id, "enabled": True},
            })))
            if response.get("result") == "OK":
                pending.remove(addon_id)
        if not pending or monitor.waitForAbort(0.25):
            break
    return sorted(pending)


def show_repos():
    """Multiselect repo picker. Installs chosen repos, then refreshes the addon DB."""
    dialog = xbmcgui.Dialog()
    labels = []
    for repo in REPOS:
        state = "[COLOR limegreen]installed[/COLOR]" if _has_addon(repo["addon_id"]) else "[COLOR gray]not installed[/COLOR]"
        labels.append("%s  -  %s  (%s)" % (repo["name"], repo["provides"], state))

    preselect = []
    picked = dialog.multiselect("Foundry - Choose Repositories to Install", labels, preselect=preselect)
    # NOTE (Android TV): multiselect OK lives in the right panel - DPAD to it; BACK cancels (None)
    if picked is None:
        return
    if not picked:
        return

    progress = xbmcgui.DialogProgress()
    progress.create("Foundry Repositories", "Working...")
    total = len(picked)
    failed = []
    installed = []
    for idx, i in enumerate(picked):
        repo = REPOS[i]
        pct = int((idx / float(total)) * 100)
        progress.update(pct, "Installing %s..." % repo["name"])
        if progress.iscanceled():
            break
        if _install_from_bundled(repo) or install_repo(repo):
            installed.append(repo["addon_id"])
        else:
            failed.append(repo["name"])
    # Registration is async: UpdateLocalAddons triggers Kodi's DB scan.
    # Do not poll Addon(id) - skins/repos can take 15-20s to register.
    failed.extend(_register_repos(installed))
    progress.update(100, "Done")
    progress.close()

    if failed:
        dialog.ok(
            "Foundry Repositories",
            "Installed with %d failure(s):[CR][CR]%s[CR][CR]Check the Kodi log for details."
            % (len(failed), "[CR]".join(failed)),
        )
    else:
        dialog.notification(
            "Foundry Repositories",
            "Repositories installed. Add-ons become available shortly.",
            xbmcgui.NOTIFICATION_INFO,
            5000,
        )
