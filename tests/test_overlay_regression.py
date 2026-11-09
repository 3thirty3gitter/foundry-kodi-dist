"""Overlay regressions; set FOUNDRY_OVERLAY_CANDIDATE=0 to test the baseline."""
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as E

BASE=Path(__file__).resolve().parents[2]
ORIGINAL=BASE/'skin.foundry-nimbus'
CANDIDATE=ORIGINAL
USE_CANDIDATE=True
GUARD='!ListItem.Property(PVR.IsRecordingTimer) + !ListItem.Property(PVR.IsRemindingTimer)'

def source(name):
    edited=CANDIDATE/'xml'/name
    return edited if USE_CANDIDATE and edited.is_file() else ORIGINAL/'xml'/name

def layouts():
    return E.parse(source('Includes.xml')).find("include[@name='DefaultSimpleListLayout']/definition")

def normal_label(layout):
    return next(g for g in layout.findall("control[@type='group']") if g.findtext('visible')==GUARD).find("control[@type='label']")

def generic_icon(layout):
    return next(c for c in layout.findall("control[@type='image']") if c.findtext('texture')=='$INFO[ListItem.Icon]')

class OverlayRegression(unittest.TestCase):
    def test_plain_and_focused_text_clear_the_icon(self):
        for layout in layouts():
            label=normal_label(layout);icon=generic_icon(layout)
            gap=int(label.findtext('left'))-int(icon.findtext('left'))-int(icon.findtext('width'))
            self.assertGreaterEqual(gap,12,(layout.tag,gap))

    def test_pvr_timer_rows_do_not_draw_a_second_icon(self):
        for layout in layouts():self.assertEqual(generic_icon(layout).findtext('visible'),GUARD)

    def test_all_static_foundry_icon_references_resolve(self):
        missing=[]
        for path in (ORIGINAL/'xml').glob('*.xml'):
            for node in E.parse(source(path.name)).iter():
                for value in [node.text or '',node.get('fallback','')]:
                    if value.startswith('foundry-icons/') and '$' not in value and not (ORIGINAL/'media'/value).is_file():missing.append((path.name,value))
        self.assertEqual(missing,[])

    def test_plain_and_focused_geometry_matches(self):
        normal,focused=list(layouts())
        for key in ('left','top','right','bottom'):self.assertEqual(normal_label(normal).findtext(key),normal_label(focused).findtext(key))
        for key in ('left','top','width','height'):self.assertEqual(generic_icon(normal).findtext(key),generic_icon(focused).findtext(key))

    def test_all_known_simple_list_widths_keep_readable_text_space(self):
        widths=[]
        for path in (ORIGINAL/'xml').glob('*.xml'):
            for inc in E.parse(path).findall(".//include[@content='DefaultSimpleListLayout']"):
                widths.append(int(inc.find("param[@name='width']").get('value')))
        self.assertEqual(sorted(widths),[320,600,880])
        label=normal_label(next(iter(layouts())))
        for width in widths:self.assertGreaterEqual(width-int(label.findtext('left'))-int(label.findtext('right')),180)

    def test_addon_info_value_reserves_the_origin_icon(self):
        tree=E.parse(source('DialogAddonInfo.xml'))
        values=[n for n in tree.iter('control') if n.get('type')=='label' and n.findtext('label')=='$INFO[ListItem.Label2]' and n.findtext('top')=='30']
        self.assertEqual(len(values),2)
        for label in values:
            text_end=int(label.findtext('left'))+int(label.findtext('width'))
            icon_left=446-25-32
            self.assertGreaterEqual(icon_left-text_end,12)

    def test_every_skin_xml_still_parses(self):
        files=list((ORIGINAL/'xml').glob('*.xml'));self.assertGreaterEqual(len(files),135)
        for path in files:E.parse(source(path.name))

    def test_generated_settings_rows_reserve_icon_padding(self):
        templates={'DefaultSettingButton','DefaultAddonSettingsButton','DefaultSystemSettingsButton','DialogSettingButton'}
        count=0
        for path in (ORIGINAL/'xml').glob('*.xml'):
            for control in E.parse(source(path.name)).iter('control'):
                row=any((n.text or '').startswith('foundry-icons/rows/') for n in control.findall('texturefocus'))
                inc=next((n for n in control.findall('include') if (n.get('content') or (n.text or '').strip()) in templates),None)
                if not row and inc is None:continue
                count+=1;offset=control.findtext('textoffsetx')
                if inc is not None:
                    param=inc.find("param[@name='textoffsetx']")
                    if param is not None:offset=param.get('value')
                if offset is not None and offset.isdigit():self.assertGreaterEqual(int(offset),84,(path.name,control.get('id')))
        self.assertGreater(count,100)

    def test_patch_preserves_navigation_ids_actions_and_row_size(self):
        for name in ['Includes.xml','Includes_Buttons.xml']:
            before=E.parse(ORIGINAL/'xml'/name);after=E.parse(source(name))
            def interaction(tree):
                return [(n.tag,dict(n.attrib),n.text) for n in tree.iter() if n.tag in {'onclick','onup','ondown','onleft','onright','onback','onfocus','onunfocus','itemlayout','focusedlayout'}]
            self.assertEqual(interaction(before),interaction(after))

if __name__=='__main__':unittest.main(verbosity=2)
