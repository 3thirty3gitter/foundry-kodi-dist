"""Offline contracts for native runner fixtures; no Kodi launch or network."""
import ast
import importlib.util
from pathlib import Path
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class NativeRunnerContracts(unittest.TestCase):
    def test_embedded_kodi_fixtures_compile(self):
        for name in ('render_library','render_interface'):
            source=(ROOT/'tools'/(name+'.py')).read_text(encoding='utf-8')
            tree=ast.parse(source)
            fixture=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FIXTURE' for t in n.targets))
            compile(fixture,name+'-fixture','exec')
            self.assertIn("(ROOT/'release.json').read_text()",source)
            self.assertNotIn("releases/1.3.9-qa",source)
            self.assertIn('XDG_CONFIG_HOME',source)
            self.assertIn('TemporaryDirectory',source)

    def test_first_paint_is_observed_without_tick_and_back_checks_native_parent(self):
        fixture=load('render_library').FIXTURE
        opening=fixture[fixture.index('source=Source();source.initial='):fixture.index("(BASE/'back-once.json')")]
        self.assertNotIn('window.tick()',opening)
        self.assertIn("window.getListSize()",opening)
        self.assertIn("window.dispose();xbmc.sleep(600)",opening)
        self.assertIn("first['after_back_and_dispose']==parent",opening)

    def test_shipped_home_restoration_is_explicitly_inside_disposable_profile(self):
        fixture=load('render_interface').FIXTURE
        self.assertIn("BASE/'kodi/portable_data/addons/skin.foundry/xml/Home.xml'",fixture)
        self.assertIn('target.resolve().is_relative_to(BASE.resolve())',fixture)
        self.assertNotIn("HELPER.parent/'skin.foundry",fixture)

    def test_sounds_use_real_migration_with_silent_and_custom_cases(self):
        fixture=load('render_interface').FIXTURE
        self.assertIn('from modules.experience import configure_experience',fixture)
        self.assertIn("('','')",fixture)
        self.assertIn('resource.uisounds.foundry.qacustom',fixture)
        self.assertIn('Settings.GetSettingValue',fixture)

    def test_animation_gate_accepts_visible_moving_frames(self):
        frames=[Image.new('RGB',(16,16),(v,0,0)) for v in (130,180,140,210)]
        self.assertEqual(load('render_interface').animation_evidence(frames,[.02]*4,1),[256]*3)

    def test_animation_gate_rejects_frozen_dark_or_unresponsive_samples(self):
        gate=load('render_interface').animation_evidence
        moving=[Image.new('RGB',(16,16),(v,0,0)) for v in (130,180,140,210)]
        dark=[Image.new('RGB',(16,16),(v,0,0)) for v in (10,30,50,70)]
        for frames,latencies,elapsed in ((moving[:1]*4,[.01],1),(dark,[.01],1),(moving,[2.1],1),(moving,[.01],21)):
            with self.assertRaises(AssertionError):gate(frames,latencies,elapsed)


if __name__=='__main__':unittest.main()
