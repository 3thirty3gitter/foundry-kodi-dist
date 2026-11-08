"""Seek feedback contracts without launching or remapping Kodi."""
from pathlib import Path
import re,unittest,xml.etree.ElementTree as E
import test_release as kodi

OSD_PATH=kodi.SKIN/'xml/Includes_StreamPilotOSD.xml'

def condition(text, state):
    # The seek tests use only native booleans and String.IsEmpty predicates.
    text=re.sub(r'String.IsEmpty\(([^)]+)\)',lambda m:str(not state.get(m[1],'')),text)
    text=re.sub(r'Player.HasPerformedSeek\((\d+)\)',lambda m:str(state.get('recent',False)),text)
    for token in ('VideoPlayer.HasEPG','Player.Seeking','Player.Paused','Player.Forwarding','Player.Rewinding'):
        text=text.replace(token,str(bool(state.get(token,False))))
    text=text.replace('+',' and ').replace('|',' or ').replace('!',' not ').replace('[','(').replace(']',')')
    if re.search(r'[^()\s]|$',text):
        assert re.fullmatch(r'[\s()A-Za-z]+',text),text
    return bool(eval(text,{'__builtins__':{}},{}))

class SeekFeedback(unittest.TestCase):
    def setUp(self):self.root=E.parse(OSD_PATH).getroot()

    def card(self,name):return self.root.find("include[@name='%s']/control"%name)

    def test_both_current_cards_render_native_signed_seek_status(self):
        for name in ('StreamPilotVODCard','StreamPilotLiveCard'):
            labels=[c for c in self.card(name).iter('control') if c.findtext('label')=='$VAR[SeekLabel]']
            self.assertEqual(len(labels),1,name)
            label=labels[0]
            self.assertEqual(label.get('type'),'label')
            self.assertIsNone(label.get('id'))
            self.assertEqual(label.findall('onclick'),[])
            for state in ({'Player.Seeking':True},{'recent':True},{'Player.Forwarding':True},{'Player.Rewinding':True}):
                self.assertTrue(condition(label.findtext('visible'),state))
            self.assertFalse(condition(label.findtext('visible'),{}))
            self.assertFalse(condition(label.findtext('visible'),{'Player.Paused':True}))

    def test_seek_pending_time_and_committed_playback_time_have_separate_bindings(self):
        variable=self.root.find("variable[@name='FoundryOSDPlaybackTime']")
        self.assertIsNotNone(variable)
        values=variable.findall('value')
        self.assertEqual(values[0].get('condition'),'Player.Seeking')
        self.assertIn('Player.SeekTime',values[0].text)
        self.assertIn('Player.Time',values[-1].text)
        self.assertIn('Player.Duration',values[0].text)
        self.assertTrue(any(c.text=='$VAR[FoundryOSDPlaybackTime]' for c in self.card('StreamPilotVODCard').iter('label')))

    def test_live_feedback_uses_epg_target_without_replacing_live_progress(self):
        variable=self.root.find("variable[@name='FoundryOSDLiveSeekTime']")
        self.assertIsNotNone(variable)
        self.assertIn('PVR.EpgEventSeekTime',variable.find('value').text)
        self.assertTrue(any(c.text=='PVR.EpgEventProgress' for c in self.card('StreamPilotLiveCard').iter('info')))

    def test_pending_seek_progress_is_distinct_from_current_progress(self):
        card=self.card('StreamPilotVODCard')
        current=next(c for c in card.iter('control') if c.findtext('info')=='Player.Progress')
        pending=next((c for c in card.iter('control') if c.findtext('info')=='Player.Seekbar'),None)
        self.assertIsNotNone(pending)
        self.assertEqual(current.findtext('visible'),'!Player.Seeking')
        self.assertEqual(pending.findtext('visible'),'Player.Seeking')
        for field in ('left','top','width','height'):
            self.assertEqual(current.findtext(field),pending.findtext(field))

    def test_new_feedback_fits_existing_cards_and_preserves_button_geometry(self):
        for name,status_bottom,button_top in (('StreamPilotVODCard',52,67),('StreamPilotLiveCard',236,80)):
            card=self.card(name)
            self.assertLessEqual(status_bottom,int(card.findtext('height')))
            labels=[c for c in card.iter('control') if (c.findtext('description') or '').startswith('Foundry ')]
            self.assertTrue(labels)
            for label in labels:
                self.assertLessEqual(int(label.findtext('top'))+int(label.findtext('height')),int(card.findtext('height')))
            buttons=card.findall("control[@type='button']")
            self.assertEqual(min(int(b.findtext('top')) for b in buttons),button_top)
        self.assertEqual([self.card('StreamPilotVODCard').findtext(f) for f in ('left','right','bottom','height')],['60','60','44','202'])
        self.assertEqual([self.card('StreamPilotLiveCard').findtext(f) for f in ('left','right','bottom','height')],['60','60','48','248'])

    def test_existing_seek_label_reads_positive_negative_and_chapter_offsets(self):
        variables=E.parse(kodi.SKIN/'xml/Variables_Seekbar.xml')
        values=variables.find("variable[@name='SeekLabel']").findall('value')
        for pending in (True,False):
            for offset in ('+00:10','-00:10','+10:00','-10:00'):
                state={'Player.SeekStepSize':offset if pending else '',
                       'Player.SeekOffset':offset,'recent':not pending}
                chosen=next(v for v in values if not v.get('condition') or condition(v.get('condition'),state))
                self.assertIn('Player.SeekStepSize' if pending else 'Player.SeekOffset',chosen.text)

    def test_seek_dialog_remains_visible_after_osd_dismissal_and_suppresses_settings(self):
        visible=E.parse(kodi.SKIN/'xml/DialogSeekBar.xml').findtext('visible')
        self.assertIn('Player.Seeking | Player.Forwarding | Player.Rewinding | Player.HasPerformedSeek(2)',visible)
        for name in ('osdaudiosettings','osdsubtitlesettings','osdvideosettings','subtitlesearch'):
            self.assertIn('Window.IsActive('+name+')',visible)
        # Dismissal only suppresses paused cards, not a new directional seek.
        self.assertIn('[Player.Paused + !Skin.HasSetting(Disable.PauseOSD) + !String.IsEqual',visible)


    def test_playback_logo_is_top_right_with_preserved_aspect_ratio(self):
        logo=self.root.find("include[@name='FoundryPlaybackStudioLogo']/control")
        self.assertIsNotNone(logo)
        self.assertEqual((logo.findtext('right'),logo.findtext('top')),('60','40'))
        self.assertEqual((logo.findtext('width'),logo.findtext('height')),('320','110'))
        self.assertIsNone(logo.find('left'))
        self.assertEqual(logo.findtext('aspectratio'),'keep')
        self.assertEqual(logo.find('aspectratio').get('align'),'right')
        self.assertEqual(logo.get('type'),'image')
        self.assertEqual(logo.findtext('texture'),'$VAR[FoundryPlaybackStudioLogo]')

    def test_logo_uses_current_player_metadata_and_never_focused_library_art(self):
        logo=self.root.find("variable[@name='FoundryPlaybackStudioLogo']")
        self.assertIsNotNone(logo)
        values=logo.findall('value')
        self.assertIn('$EXP[FoundryPlayerCurrentItem]',values[0].get('condition'))
        self.assertIn('foundry.player.studiologo',values[0].text)
        self.assertEqual([v.text for v in values[1:4]],[
            '$INFO[Player.Art(studiologo)]','$INFO[Player.Art(studio.logo)]',
            '$INFO[Player.Art(tvshow.studiologo)]'])
        self.assertFalse(values[-1].text)
        text=E.tostring(logo,encoding='unicode')
        self.assertNotIn('ListItem',text)
        self.assertNotIn('foundry.metadata.',text)
        control=self.root.find("include[@name='FoundryPlaybackStudioLogo']/control")
        self.assertIn('!VideoPlayer.Content(livetv)',control.findtext('visible'))

    def test_both_playback_surfaces_include_one_studio_logo_without_changing_cards(self):
        for name in ('VideoOSD','DialogSeekBar'):
            path=OSD_PATH.parent/(name+'.xml')
            doc=E.parse(path)
            self.assertEqual([c.text for c in doc.findall('controls/include')].count('FoundryPlaybackStudioLogo'),1)
            self.assertEqual({c.text for c in doc.findall('controls/control/include')},
                             {'StreamPilotVODCard','StreamPilotLiveCard'})
