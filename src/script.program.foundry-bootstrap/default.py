"""Compatibility shortcut for existing Foundry bootstrap installations."""
import xbmc

if __name__ == "__main__":
    xbmc.executebuiltin("RunScript(script.program.foundry-build)")
