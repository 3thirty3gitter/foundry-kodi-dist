"""Merge owner-requested File Manager bookmarks; never install repository code."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def merge_sources(data, entries):
    root = ET.fromstring(data) if data.strip() else ET.Element('sources')
    if root.tag != 'sources':
        raise ValueError('Unexpected sources document')
    files = root.find('files')
    if files is None:
        files = ET.SubElement(root, 'files')
    existing = {p.text.rstrip('/') for p in files.findall('source/path') if p.text}
    changed = False
    for entry in entries:
        if entry['url'].rstrip('/') in existing:
            continue
        source = ET.SubElement(files, 'source')
        ET.SubElement(source, 'name').text = entry['name']
        ET.SubElement(source, 'path', pathversion='1').text = entry['url']
        ET.SubElement(source, 'allowsharing').text = 'true'
        existing.add(entry['url'].rstrip('/'))
        changed = True
    return ET.tostring(root, encoding='unicode'), changed


def ensure_file_sources():
    """Optional Slate skin never changes global Kodi configuration."""
    return False
