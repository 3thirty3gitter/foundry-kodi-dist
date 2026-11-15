"""Assert and reverse only the explicitly approved media-selector XML deltas."""
import copy

def normalized(node):
    return node.tag, dict(node.attrib), (node.text or '').strip(), [normalized(c) for c in node]

def strip_media_context(root):
    found = 0
    for parent in root.iter():
        for child in list(parent):
            if child.tag != 'param' or child.get('name') != 'media_context':
                continue
            assert parent.tag == 'include' and parent.get('content') == 'MediaFlags'
            assert child.attrib == {'name':'media_context','value':'container'} and not list(child) and not (child.text or '').strip()
            assert [(p.attrib) for p in parent.findall("param[@name='infolabel_prefix']")] == [{'name':'infolabel_prefix','value':'Container.'}]
            assert [(p.attrib) for p in parent.findall("param[@name='resolution_var']")] == [{'name':'resolution_var','value':'$VAR[ContainerResolutionFlagVar]'}]
            parent.remove(child); found += 1
    assert found <= 1
    return root

def wide_guard(prefix='foundry.media'):
    prop=prefix+'.player.audiocodec'
    return f'String.IsEqual(Window(Home).Property({prop}.wide),true) + !String.IsEmpty(Window(Home).Property({prop}.path)) + String.IsEqual(Skin.String(MediaIconPack),Window(Home).Property({prefix}.pack)) + String.IsEqual(VideoPlayer.AudioCodec,Window(Home).Property({prop}.value))'

def strip_live_media_layout(root,prefix='foundry.media'):
    guard=wide_guard(prefix)
    # Each alternate must be an exact duplicate of its builtin group except for
    # the sole approved dimension and mutually exclusive guard.
    for tag,old,new in [('right','452','536'),('width','248','332')]:
        built=[c for c in root.findall('control') if c.get('type')=='group' and c.findtext(tag)==old]
        expanded=[c for c in root.findall('control') if c.get('type')=='group' and c.findtext(tag)==new]
        assert len(built)==len(expanded)==1
        a,b=built[0],expanded[0]
        assert [n.text for n in a.findall('visible')]==['!['+guard+']']
        assert [n.text for n in b.findall('visible')]==[guard]
        left,right=copy.deepcopy(a),copy.deepcopy(b)
        left.remove(left.find('visible'));right.remove(right.find('visible'));right.find(tag).text=old
        assert normalized(left)==normalized(right)
        if tag=='right':
            assert (a.findtext('left'),a.findtext('top'),a.findtext('height'))==('228','28','192')
        else:
            assert (a.findtext('right'),a.findtext('top'),a.findtext('height'),a.findtext('include'))==('164','115','54','StreamPilotFormatBadges')
        root.remove(b);a.remove(a.find('visible'))
    return root
