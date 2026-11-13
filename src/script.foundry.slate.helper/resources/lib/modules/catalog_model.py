"""Pure catalog state shared by the custom Kodi window and regression tests."""
from dataclasses import dataclass, field
import math
import re

PAGE_SIZE = 20
SORTS = (("date_asc", "Date · Oldest first"), ("date_desc", "Date · Newest first"),
         ("title_asc", "Alphabetical · A-Z"), ("title_desc", "Alphabetical · Z-A"))


def clean(value):
    text = str(value or "").strip()
    return "" if text.casefold() in {"n/a", "none", "null"} else text


def label(item):
    return clean(item.get("title") or item.get("label"))


def date(item):
    value = clean((item.get("firstaired") if item.get("type")=="episode" else "") or item.get("premiered") or item.get("releasedate") or item.get("year"))
    return value if re.match(r"^\d{4}", value) else ""


def ordered(items, order):
    if order not in dict(SORTS):
        return list(items)
    result = sorted(items, key=lambda i: (label(i).lower(),clean(i.get('file'))))
    if order.startswith("title"):
        return result if order == "title_asc" else list(reversed(result))
    # Unknown dates stay last in BOTH directions, as in StreamPilot's comparator.
    known = [i for i in result if date(i)]
    unknown = [i for i in result if not date(i)]
    return sorted(known, key=date, reverse=order == "date_desc") + unknown


@dataclass
class CatalogState:
    items: list = field(default_factory=list)
    page: int = 1
    selected: int = 0
    order: str = ""
    query: str = ""
    generation: int = 0
    next_path: str = ""
    previous_path: str = ""
    server_page: int = 1
    server_total_pages: int = 0

    def filtered(self):
        query = self.query.strip().casefold()
        return ordered([i for i in self.items if not query or query in label(i).casefold()], self.order)

    @property
    def total_pages(self):
        return max(1, math.ceil(len(self.filtered()) / PAGE_SIZE))

    def page_items(self):
        self.page = max(1, min(self.page, self.total_pages))
        start = (self.page - 1) * PAGE_SIZE
        return self.filtered()[start:start + PAGE_SIZE]

    def rail(self):
        result = []
        if self.page > 1 or self.previous_path:
            result.append({"kind": "previous", "label": "BACK"})
        result.extend(dict(i, kind="media") for i in self.page_items())
        if self.page < self.total_pages or self.next_path:
            result.append({"kind": "next", "label": "NEXT"})
        return result

    def set_sort(self, value):
        if value not in dict(SORTS):
            raise ValueError("Unknown catalog sort")
        if self.order == value:
            return False
        self.order, self.page, self.selected = value, 1, 0
        self.generation += 1
        return True

    def set_query(self, value):
        value = str(value or "").strip()
        if value == self.query:
            return False
        self.query, self.page, self.selected = value, 1, 0
        self.generation += 1
        return True

    def move_page(self, direction):
        if direction not in {"next", "previous"}:
            raise ValueError("Unknown page action")
        self.page = max(1, min(self.total_pages, self.page + (1 if direction == "next" else -1)))
        self.selected = 0

    def page_label(self):
        number = self.server_page if self.next_path or self.previous_path else self.page
        return "Page %d" % number



def pagination_kind(item):
    if item.get('filetype')!='directory':return ''
    name=re.sub(r'\[/?[^]]+\]','',clean(item.get('label'))).strip().casefold()
    name=name.strip(' <>»«→←⟵⟶')
    suffix=r'(?:\s*[:#-]?\s*\(?\d+(?:\s*(?:/|of)\s*\d+)?\)?)?'
    if re.fullmatch(r'next(?:\s+page)?'+suffix,name):return 'next'
    if re.fullmatch(r'(?:previous(?:\s+page)?|back(?:\s+page)?)'+suffix,name):return 'previous'
    return ''


def split_directory(items):
    """Keep provider URLs intact; never infer or rewrite undocumented query args."""
    media, next_path, previous_path = [], "", ""
    for item in items:
        name = re.sub(r"\[/?[^]]+\]", "", clean(item.get("label"))).strip().casefold()
        page_kind=pagination_kind(item)
        if page_kind=='next':
            next_path = clean(item.get("file"))
        elif page_kind=='previous':
            previous_path = clean(item.get("file"))
        elif name not in {"..", "..."}:
            media.append(dict(item))
    return media, next_path, previous_path
