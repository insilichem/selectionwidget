#!/usr/bin/env python
# encoding: utf-8

# Get used to importing this in your Py27 projects!
from __future__ import print_function, division 
# Python stdlib
import Tkinter as tk
import string
import re
from itertools import cycle
from collections import OrderedDict

class SelectionEntry(tk.Text):
    
    _STYLE = {'height': 1, 'background': 'white', 'borderwidth': 1, 
              'highlightthickness': 0, 'insertwidth': 1}
    _SPECIAL_KEYS = ('??', 'Alt_L', 'Caps_Lock', 'Control_L',
                    'Control_R', 'Down', 'End', 'F1', 'F2', 'F3',
                    'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
                    'Home', 'Insert', 'Left', 'Menu', 'Next', 'Num_Lock', 
                    'Pause', 'Prior', 'Right', 'Scroll_Lock', 'Shift_L', 
                    'Shift_R', 'Super_L', 'Super_R', 'Up')
    _NORMAL_KEYS = string.letters + string.digits + '@:./-;,!?_'
    
    PALETTE = ('blue', 'red', 'purple', 'sienna', 'grey', 'green', 'turquoise', 'gold')
    PALETTE_HEX = ('#0000ff', '#ff0000', '#a020f0', '#a0522d',
                   '#708090', '#00ff00', '#40e0d0', '#ffd700')
    WRONG = 'wrong'

    def __init__(self, parent=None, validator=None, splitter=r'(\s+)', item_creator=None, **kwargs):
        # Init and configure base widget
        tk.Text.__init__(self, parent, **kwargs)
        self.configure(**self._STYLE)
        
        # Callables
        self.validator = validator if validator else self._identity
        self.item_creator = item_creator

        # Model
        self.items = []
        self.objects = OrderedDict()

        # Tags & Markers
        self.colors = cycle(iter(self.PALETTE))
        self.tag_config(self.WRONG, background='red', foreground='white')
        for name, color in zip(self.PALETTE, self.PALETTE_HEX):
            self.tag_config(name, foreground=color)
        self.reset_highlight_marks()

        # Privates
        self._re = re.compile(splitter)
        self._callbacks = []
        self._clear_callbacks = []

        # Triggers
        self.bind('<KeyRelease>', self.on_key_release)

    def _identity(self, item):
        return item

    def on_key_release(self, event=None):
        if event.keysym in self._SPECIAL_KEYS:
            return
        self.itemize()
        
    def do_callbacks(self, *items):
        if not items:
            items = self.items
        for fn in self._callbacks:
            fn(*items)

    def add_callback(self, fn):
        self._callbacks.append(fn)

    def do_clear_callbacks(self, *items):
        if not items:
            items = self.items
        for fn in self._clear_callbacks:
            fn(*items)

    def add_clear_callback(self, fn):
        self._clear_callbacks.append(fn)

    def itemize(self, a=None, b=None, c=None, highlight=True, callback=True):
        self.clear_items()
        specs = self.split_specs()
        for spec, sep in map(None, specs[::2], specs[1::2]):
            sep = sep if sep else ''
            self.add_item(text=spec, sep=sep, highlight=False, callback=False)
        if highlight:
            self.highlight_all_text()
        if callback:
            self.do_callbacks()

    def rebuild_tags(self):
        self.reset_colors()
        for item in self.items:
            item.tag = self.next_color()
        self.highlight_all_text()

    def highlight(self, item, start=None):
        if start is None:
            start = self.search(item.text, 1.0, stopindex='end')
        if start is not None:
            self.tag_add(item.tag, start, '{}+{}c'.format(start, len(item.text)))
    
    def highlight_all_matches(self, item, start=None):
        start = start if start is not None else 1.0
        while True:
            pos = self.search(item.text, start, stopindex='end')
            if not pos:
                break
            self.tag_add(item.tag, pos, '{}+{}c'.format(pos, len(item.text)))
    
    def highlight_all_text(self):
        self.clear_highlight()
        self.reset_highlight_marks()
        for item in self.items:
            self.mark_set('hl_end', 'hl_start+{}c'.format(len(item.text)))
            self.highlight(item, 'hl_start')
            self.mark_set('hl_start', 'hl_end+{}c'.format(len(item.sep)))
    
    def clear_highlight(self):
        for tag in self.tag_names():
            self.tag_remove(tag, 1.0, 'end')

    @property
    def content(self):
        return self.get(1.0, 'end-1c').strip('\n')
    
    def split_specs(self):
        return [q for q in self._re.split(self.content) if q]

    def next_color(self):
        return next(self.colors)

    def reset_colors(self):
        self.colors = cycle(iter(self.PALETTE))
    
    def reset_highlight_marks(self):
        self.mark_set('hl_start', '1.0')
        self.mark_set('hl_end', 'end')

    def clear_items(self):
        self.items = []
        self.objects.clear()
        self.do_clear_callbacks()
        self.reset_colors()

    def add_item(self, text=None, sep=' ', obj=None, highlight=True, insert=False, callback=True):
        item = self.item_creator(text=text, sep=sep, obj=obj, validator=self.validator, parent=self)
        item.validate()
        if item.ok:
            try:
                sameitems = self.objects[item.obj]
            except KeyError:
                self.objects[item.obj] = [item]
                item.tag = self.next_color()
            else:
                sameitems.append(item)
                item.tag = sameitems[0].tag
        else:
            item.tag = self.WRONG
        self.items.append(item)
        if insert:
            self.insert('insert', item.text + item.sep)
        if highlight:
            self.highlight(item)
        if callback:
            self.do_callbacks(item)


class SelectionItem(object):

    def __init__(self, text=None, sep=' ', tag=None, obj=None, validator=None, parent=None):
        self.parent = parent
        self.text = text
        self.sep = sep
        self.tag = tag
        self.obj = obj
        self.validator = validator
        if obj:
            self._ok = True 
            if text is None:
                self.text = self.specifier(obj)
        else:
            self._ok = False

    def validate(self):
        if self.obj is None:
            self.obj = self.validator(self.text)
            self._ok = True if self.obj else False

    @property
    def ok(self):
        if self._ok is None:
            self.validate(self.text)
        return self._ok

    def __str__(self):
        return self.text + self.sep

    def specifier(self, obj):
        return str(obj)

    def delete(self):
        print('Deleting', repr(self))
        self.parent.items.remove(self)
        if self.ok:
            while True:
                pos = self.parent.search(self.text, 1.0, stopindex='end')
                if not pos:
                    break
                self.parent.delete(pos, '{}+{}c'.format(pos, len(self.text) + len(self.sep)))
            del self.parent.objects[self.obj]
