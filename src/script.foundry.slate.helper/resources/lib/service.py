import xbmc, xbmcgui, xbmcvfs
from threading import Thread
from modules.logger import logger
from modules.file_sources import ensure_file_sources
from modules.startup_splash import install_startup_splash

from modules.monitors.ratings import RatingsMonitor
from modules.monitors.metadata import MetadataMonitor
from modules.vod import CatalogArtworkMonitor, CatalogRoutingMonitor
from modules.monitors.image import ImageMonitor, ImageBlur, ImageAnalysisConfig
from modules.databases.ratings import RatingsDatabase
from modules.config import SETTINGS_PATH


class Service(xbmc.Monitor):
    """Main service class that coordinates monitor and rating lookups."""

    def __init__(self):
        super().__init__()
        self._initialize()

    def _initialize(self):
        """Initialize service components."""
        if not xbmcvfs.exists(SETTINGS_PATH):
            xbmcvfs.mkdirs(SETTINGS_PATH)

        self.home_window = xbmcgui.Window(10000)
        self.get_infolabel = xbmc.getInfoLabel
        self.get_visibility = xbmc.getCondVisibility
        self.image_monitor = ImageMonitor(ImageBlur, ImageAnalysisConfig())
        self.ratings_monitor = RatingsMonitor(RatingsDatabase(), self.home_window)
        self.metadata_monitor = MetadataMonitor(self.home_window)
        self.vod_artwork_monitor = CatalogArtworkMonitor()
        self.catalog_routing_monitor = CatalogRoutingMonitor()

    def run(self):
        """Start the service and monitor."""
        self.image_monitor.start()
        sources_attempted = False
        splash_attempted = False
        try:
            while not self.abortRequested():
                if self._should_pause():
                    self.metadata_monitor.pause()
                    self.waitForAbort(2)
                    continue
                if not sources_attempted:
                    ensure_file_sources()
                    sources_attempted = True
                if not splash_attempted:
                    try:
                        pass  # Slate must not replace Foundry global startup splash.
                    except (OSError, ValueError, RuntimeError) as error:
                        xbmc.log("[Foundry] Startup splash setup failed: %s" % error, xbmc.LOGERROR)
                    splash_attempted = True
                self.catalog_routing_monitor.process()
                self.vod_artwork_monitor.process_current_item()
                self.metadata_monitor.process_current_item()
                self.ratings_monitor.process_current_item()
                self.waitForAbort(0.2)
        finally:
            self.metadata_monitor.stop()
            self.image_monitor.stop()
            self.image_monitor.join(timeout=2)

    def _should_pause(self):
        """Determine if service should pause."""
        if self.home_window.getProperty("slate_pause_services") == "true":
            return True

        if xbmc.getSkinDir() != "skin.foundry.slate":
            return True

        if not self.get_visibility(
            "String.IsEqual(Window(Home).Property(foundry.slate.catalog.active),true) | Window.IsVisible(videos) | Window.IsVisible(favouritesbrowser) | Window.IsVisible(home) | Window.IsVisible(11121) | Window.IsActive(movieinformation) | Player.HasVideo"
        ):
            return True

        return False

    def onNotification(self, sender, method, data):
        """Handle Kodi notifications."""
        # logger(
        #     "Notification received - Sender: {}, Method: {}, Data: {}".format(
        #         sender, method, data
        #     ),
        #     1,
        # )
        if sender == "xbmc":
            if method in ("GUI.OnScreensaverActivated", "System.OnSleep"):
                self.home_window.setProperty("slate_pause_services", "true")
            elif method in ("GUI.OnScreensaverDeactivated", "System.OnWake"):
                self.home_window.clearProperty("slate_pause_services")

    def onSettingsChanged(self):
        # Key removal/change also invalidates cache while browsing is paused.
        self.metadata_monitor.refresh_config()


if __name__ == "__main__":
    service = Service()
    service.run()
