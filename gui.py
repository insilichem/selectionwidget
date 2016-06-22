#!/usr/bin/env python
# encoding: utf-8

# Get used to importing this in your Py27 projects!
from __future__ import print_function, division 
# Python stdlib
import Tkinter as tk
import string
import re
# Chimera stuff
import chimera
from chimera.baseDialog import ModelessDialog
from chimera.specifier import evalSpec
from chimera.selection import (clearCurrent as clear_selection, addCurrent as add_to_current_selection,
                               currentContents as current_selection_contents)
from chimera.colorTable import (colors as chimera_colors, getTkColorByName as tk_color,
                                getColorByName as chimera_color)
from Midas import focus
# Additional 3rd parties

"""
An Excel-like selection dialog for UCSF Chimera
"""

ui = None
def showUI(callback=None):
    """
    Requested by Chimera way-of-doing-things
    """
    if chimera.nogui:
        tk.Tk().withdraw()
    global ui
    if not ui: # Edit this to reflect the name of the class!
        ui = SelectionDialog()
    ui.enter()
    if callback:
        ui.addCallback(callback)

STYLES = {
    tk.Text: {
        'background': 'white',
        'borderwidth': 1,
        'highlightthickness': 0,
        'insertwidth': 1,
    },
    tk.Button: {
        'borderwidth': 1,
        'highlightthickness': 0,
    },
}

class SelectionDialog(ModelessDialog):

    """
    To display a new dialog on the interface, you will normally inherit from
    ModelessDialog class of chimera.baseDialog module. Being modeless means
    you can have this dialog open while using other parts of the interface.
    If you don't want this behaviour and instead you want your extension to 
    claim exclusive usage, use ModalDialog.
    """

    buttons = ('OK', 'Close')
    default = None
    help = 'https://www.insilichem.com'

    # Some constants
    special_keys = ['??', 'Alt_L', 'Caps_Lock', 'Control_L',
                    'Control_R', 'Down', 'End', 'F1', 'F2', 'F3',
                    'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
                    'Home', 'Insert', 'Left', 'Menu', 'Next', 'Num_Lock', 
                    'Pause', 'Prior', 'Right', 'Scroll_Lock', 'Shift_L', 
                    'Shift_R', 'Super_L', 'Super_R', 'Up']
    normal_keys = string.letters + string.digits + '@:./-;,!?_'
    allowed_modes = ('atoms', 'bonds', 'residues', 'chains', 'molecules')
    white = chimera.MaterialColor.lookup('white')
    ok_colors = ['blue', 'brown', 'dark cyan', 'dark green', 'dark grey', 
                 'dark magenta', 'dark olive green', 'dark red', 'dark slate blue',
                 'dark slate gray', 'dark slate grey', 'dim gray', 'dim grey', 
                 'firebrick', 'forest green', 'medium blue', 'navy blue', 
                 'orange red', 'purple', 'red', 'sea green', 'sienna', 
                 'slate gray', 'slate grey', 'spring green', 'turquoise', 'violet red']

    def __init__(self, parent=None, mode='atoms'):
        # Check
        if mode not in self.allowed_modes:
            raise ValueError('mode must be one of {}'.format(self.allowed_modes))
        
        self.title = 'Select {}'.format(mode)
        self.mode = mode

        # Private vars
        self._re = re.compile(r'(\s)')
        self._old_selection = current_selection_contents()
        self._colored_molecules = []

        # Fire up
        ModelessDialog.__init__(self)
        if not chimera.nogui:  # avoid useless errors during development
            chimera.extension.manager.registerInstance(self)

        # Fix styles
        self._fix_styles(*self.buttonWidgets.values())

        # Triggers
        self._handlers = {}
        self._handlers[('Model', self.desaturate_models)] = \
            chimera.triggers.addHandler('Model', self.desaturate_models, None)
        self.desaturate_models()

    def _initialPositionCheck(self, *args):
        try:
            ModelessDialog._initialPositionCheck(self, *args)
        except Exception as e:
            if not chimera.nogui:  # avoid useless errors during development
                raise e

    def _fix_styles(self, *widgets):
        for widget in widgets:
            try:
                widget.configure(**STYLES[widget.__class__])
            except Exception as e:
                print('Error fixing styles:', type(e), str(e))

    def fillInUI(self, parent):
        """
        This is the main part of the interface. With this method you code
        the whole dialog, buttons, textareas and everything.
        """
        self.canvas = tk.Frame(parent)
        self.canvas.pack()
        self.entry = tk.Text(self.canvas, width=50, height=1, **STYLES[tk.Text])
        self.entry.pack(padx=10, pady=10)
        self.entry.bind("<KeyRelease>", self.parse)
        self.entry.tag_config('wrong', background='red', foreground='white')
        
        for color in self.ok_colors:
            self.entry.tag_config(color, foreground=tk_color(color))

    def OK(self):
        """
        Default! Triggered action if you click on an OK button
        """
        self.Close()

    def Close(self):
        """
        Default! Triggered action if you click on the Close button
        """
        self.resaturate_models()
        for (trigger, key), handler in self._handlers.items():
            chimera.triggers.deleteHandler(trigger, handler)
        global ui
        ui = None
        ModelessDialog.Close(self)
        self.destroy()

    # Custom methods
    def parse(self, event):
        if event.keysym in self.special_keys:
            return
        content = event.widget.get(1.0, 'end-1c').strip('\n')
        if not content:
            return
        # Save cursor position
        cursor = self.entry.index('insert')
        queries = [q for q in self._re.split(content) if q]
        # Clear before reformatting
        self.entry.delete(1.0, 'end')
        clear_selection()

        ok_tags = iter(self.ok_colors)
        for query, sep in map(None, queries[::2], queries[1::2]):
            validated = self.validate(query)
            if validated is not None:
                tag = next(ok_tags)
                self.depict(validated, color=tag)
            else:
                tag = 'wrong'
            self.entry.insert('insert', query + (sep if sep else ''), tag)
        # Restore cursor position
        self.entry.mark_set('insert', cursor)
        current_selection = current_selection_contents()
        if self._old_selection != current_selection:
            self._old_selection = current_selection
            try:
                self.focus()
            except:
                pass

    def validate(self, query):
        try:
            sel = evalSpec(query)
        except:  # Syntax error, etc
            return
        else:
            if sel:
                current = getattr(sel, self.mode)()
                if len(current) == 1:
                    return current[0]
    
    def depict(self, item, color=None):
        atoms = [item] if self.mode == 'atoms' else item.atoms
        for a in atoms:
            add_to_current_selection(a)
            mcolor = chimera_color(color)
            print(color, mcolor)
            a.color = mcolor
    
    def focus(self):
        selected = getattr(chimera.selection, 'current' + self.mode.title())()
        if selected:
            focus('sel zr < 3')
            for item in selected:
                if self.mode == 'atoms':
                    if item.name in ('C', 'CA', 'N', 'O'):
                        item.residue.ribbonDrawMode = 3
                    for a in item.residue.atoms:
                        a.display = True
                else:
                    for a in item.atoms:
                        a.display = True
        else:
            chimera.runCommand('focus')
            self._colored_molecules = []
            self.desaturate_models()

    def desaturate_models(self, *args):
        for mol in chimera.openModels.list(modelTypes=[chimera.Molecule]):
            if mol in self._colored_molecules:
                continue
            mol._old_color = mol.color
            mol.color = None
            for a in mol.atoms:
                a._old_color = a.color
                a.color = self.white
            for r in mol.residues:
                r._old_colors = r.ribbonColor, r.fillColor
                r.color = None
            self._colored_molecules.append(mol)

    def resaturate_models(self):
        for mol in chimera.openModels.list(modelTypes=[chimera.Molecule]):
            mol.color = mol._old_color
            del mol._old_color
            for a in mol.atoms:
                a.color = a._old_color
                del a._old_color
            for r in mol.residues:
                r.ribbonColor, r.fillColor = r._old_colors
                del r._old_colors