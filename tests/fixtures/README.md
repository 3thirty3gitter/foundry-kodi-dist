# Upstream dependency fixture

Required dependency manifests captured on 2026-10-26 from:

- https://mirrors.kodi.tv/addons/omega/addons.xml.gz
- https://slyguy.uk/.repo/repository.slyguy/addons.xml
- https://raw.githubusercontent.com/not-coco-joe/repository.cocoscrapers/master/zips/addons.xml

The fixture stores only IDs, versions and required imports for the closure used by Foundry Build. It contains no add-on code or API keys.
Kodi supplies the virtual xbmc/kodi interfaces and its bundled Pillow module. Kodi selects the correct InputStream Adaptive binary for the target platform.
