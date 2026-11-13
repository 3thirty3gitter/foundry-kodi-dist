"""Normalize optional hero metadata without locale-dependent strptime imports."""
import re
from datetime import date

from .catalog_model import clean


def names(value):
    values = value if isinstance(value, (list, tuple)) else clean(value).split(' / ')
    return [clean(v) for v in values if isinstance(v, (str, int, float)) and clean(v)]


def episode_heading(item):
    if item.get('type') not in ('episode','season'):return ''
    def number(name):
        value=item.get(name)
        return int(str(value)) if not isinstance(value,bool) and re.fullmatch(r'\d+',str(value)) else None
    season,episode=number('season'),number('episode')
    code=('S%02d'%season if season is not None else '')+('E%02d'%episode if episode is not None else '')
    if item.get('type')=='season':code='Specials' if season==0 else 'Season %d'%season if season is not None else ''
    title=clean(item.get('title') or item.get('label'))
    show=clean(item.get('showtitle') or item.get('tvshowtitle'))
    return ' · '.join(dict.fromkeys(value for value in (show,code,title) if value))


def details(item, is_tv=False, media_kind=None):
    released = clean((item.get('firstaired') if item.get('type')=='episode' else '') or item.get('premiered') or item.get('firstaired') or item.get('year'))
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', released)
    if match:
        try:
            value = date(*(int(v) for v in match.groups()))
            months = ('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')
            released = '%s %d, %d' % (months[value.month-1], value.day, value.year)
        except ValueError:
            pass
    certification = clean(item.get('mpaa'))
    if certification.startswith(('CA ', 'US ')):
        certification = certification[3:]
    genre = names(item.get('genre'))[:3]
    studio = names(item.get('studio'))
    language = clean(item.get('original_language') or item.get('language')).upper()
    kind_label={'season':'TV Season','episode':'TV Episode','tvshow':'TV Series','video':'Video','musicvideo':'Music Video','movie':'Movie'}.get(media_kind or item.get('type'),'TV Series' if is_tv else 'Movie')
    try:runtime=('%d min'%(int(float(item.get('runtime') or 0))//60)) if float(item.get('runtime') or 0)>=60 else ''
    except (ValueError,TypeError):runtime=''
    return {
        'released': (('Aired ' if is_tv else 'Released ') + released) if released else '',
        'certification': certification,
        'details': '  \u2022  '.join(v for v in [episode_heading(item),kind_label,runtime, ' \u00b7 '.join(genre), ' \u00b7 '.join(studio), language] if v),
        'plot': clean(item.get('plot')) or 'No description available.',
    }
