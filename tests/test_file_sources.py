import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as E
import test_release
from modules.file_sources import merge_sources

class FileSourceBookmarks(unittest.TestCase):
    def setUp(self):
        self.entries=json.loads((Path(__file__).resolve().parents[2]/'script.foundry.helper/resources/file-sources.json').read_text())
    def test_exact_owner_urls_once(self):
        merged,changed=merge_sources('',self.entries)
        self.assertTrue(changed)
        self.assertEqual(E.fromstring(merged).findall('files/source/path')[0].text,'https://fenskeleton.github.io/zips/repository.fenskeleton/')
        again,changed=merge_sources(merged,self.entries)
        self.assertFalse(changed)
        self.assertEqual(merged,again)
    def test_existing_sources_and_other_sections_preserved(self):
        data='<sources><video><source><name>Local</name><path>/movies</path></source></video><files><source><name>Mine</name><path>https://example.test/</path></source></files></sources>'
        merged,_=merge_sources(data,self.entries);root=E.fromstring(merged)
        self.assertEqual(root.findtext('video/source/path'),'/movies')
        self.assertEqual(root.findtext('files/source/name'),'Mine')
        self.assertEqual(len(root.findall('files/source')),3)
    def test_same_url_different_name_or_trailing_slash_no_duplicate(self):
        data='<sources><files><source><name>My Repo</name><path>'+self.entries[0]['url'].rstrip('/')+'</path></source></files></sources>'
        merged,_=merge_sources(data,self.entries)
        self.assertEqual(len(E.fromstring(merged).findall('files/source')),2)
    def test_invalid_existing_document_is_rejected(self):
        with self.assertRaises(E.ParseError):merge_sources('<broken',self.entries)
        with self.assertRaises(ValueError):merge_sources('<settings/>',self.entries)
    def test_bookmark_module_has_no_install_or_enable_actions(self):
        path=Path(__file__).resolve().parents[2]/'script.foundry.helper/resources/lib/modules/file_sources.py'
        source=path.read_text()
        for action in ('InstallAddon(', 'Addons.SetAddonEnabled','UpdateAddonRepos','repo_installer'):
            self.assertNotIn(action,source)
