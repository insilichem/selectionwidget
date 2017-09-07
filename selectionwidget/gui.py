#!/usr/bin/env python
# encoding: utf-8

# Get used to importing this in your Py27 projects!
from __future__ import print_function, division 
# Python stdlib
import Tkinter as tk
from contextlib import contextmanager
# Chimera stuff
import chimera
from chimera.baseDialog import ModelessDialog
from chimera.specifier import evalSpec
from chimera.selection import (clearCurrent as clear_selection, addCurrent as add_to_current_selection,
                               removeCurrent as remove_from_current_selection)
from chimera.colorTable import getColorByName as chimera_color
from Midas import focus
# Own
from .widgets import SelectionItem, SelectionEntry

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
    help = False
    
    def __init__(self, parent=None, mode='atoms'):
        # Check
        self.title = 'Select {}'.format(mode)
        self.mode = mode

        # Fire up
        ModelessDialog.__init__(self)
        if not chimera.nogui:  # avoid useless errors during development
            chimera.extension.manager.registerInstance(self)

        # Fix styles
        self._fix_styles(*self.buttonWidgets.values())
        self._toplevel.attributes('-topmost', True)
        self._toplevel.resizable(width=True, height=False)


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
        self.canvas.pack(expand=True, fill='x')
        self.entry = ChimeraSelectionEntry(self.canvas, mode=self.mode, respond_to_focus=False, width=50)
        self.entry.pack(padx=10, pady=10, expand=True, fill='x')
        self.entry.desaturate()

    def OK(self):
        """
        Default! Triggered action if you click on an OK button
        """
        self.Close()

    def Close(self):
        """
        Default! Triggered action if you click on the Close button
        """
        chimera.viewer.background = None
        self.entry.resaturate()
        for (trigger, key), handler in self.entry._handlers.items():
            chimera.triggers.deleteHandler(trigger, handler)
        global ui
        ui = None
        ModelessDialog.Close(self)
        chimera.extension.manager.deregisterInstance(self)
        self.destroy()


# Custom widgets
class ChimeraSelectionEntry(SelectionEntry):
    
    allowed_modes = ('atoms', 'bonds', 'residues', 'chains', 'molecules')
    white = chimera.MaterialColor.lookup('white')
    white.opacity = 0.5

    def __init__(self, parent=None, mode='atoms', respond_to_focus=True, **kwargs):
        if mode not in self.allowed_modes:
            raise ValueError('mode must be one of {}'.format(self.allowed_modes))
        self.mode = mode

        SelectionEntry.__init__(self, validator=self.validate, parent=parent, **kwargs)
        self.item_creator = ChimeraItem
        self.on_selection_changed()

        # Private vars
        self._old_selection = self.current_selection()
        self._old_background = chimera.viewer.background
        self._colored_molecules = []
        self._handlers = {}
        self._depicted = []
        self._selecting = False

        # Triggers
        self._handlers[('file open', self.desaturate)] =  chimera.triggers.addHandler('file open', self.desaturate, None)
        self._handlers[('file open', self.itemize)] =  chimera.triggers.addHandler('file open', self.itemize, None)
        self._handlers[('selection changed', self.on_selection_changed_proxy)] =  chimera.triggers.addHandler('selection changed', self.on_selection_changed_proxy, None)
        if respond_to_focus:
            self.bind('<FocusIn>', self.on_focus_in)
            self.bind('<FocusOut>', self.on_focus_out)
        self.add_callback(self.depict)
        self.add_clear_callback(self.undo_depict)

    # Methods
    def validate(self, query):
        try:
            sel = evalSpec(query)
            if sel:
                current = getattr(sel, self.mode)()
                if len(current) == 1:
                    return current[0]
        except:  # Syntax error, etc
            return

    def current_selection(self):
        return getattr(chimera.selection, 'current' + self.mode.title())()

    def focus_atoms(self):
        selected = self.current_selection()
        if selected:
            focus('sel zr < 3')
        else:
            chimera.runCommand('focus')

    def depict(self, *items):
        for item in items:
            if not item.ok:
                continue
            atoms = [item.obj] if self.mode == 'atoms' else item.obj.atoms
            with self.untriggered_selection():
                add_to_current_selection(atoms)
            self._depicted.extend(atoms)
            for a in atoms:
                a.color = chimera_color(item.tag)
        self.focus_atoms()

    def undo_depict(self, *items):
        if items:
            objs = [item.obj for item in items if item.ok]
            self._depicted = [i for i in self._depicted if i in objs]
        else:
            objs = self._depicted[:]
            self._depicted = []
        for a in objs:
            a.color = self.white
        with self.untriggered_selection():
            remove_from_current_selection(objs)
         
    def desaturate(self, *args):
        chimera.viewer.background = self.white
        for mol in chimera.openModels.list(modelTypes=[chimera.Molecule]):
            if mol in self._colored_molecules:
                continue
            mol._old_color = mol.color
            mol.color = self.white
            for a in mol.atoms:
                if a not in self._depicted:
                    a._old_color = a.color
                    a.color = self.white
            for r in mol.residues:
                r._old_colors = r.ribbonColor, r.fillColor
                r.color = self.white
            self._colored_molecules.append(mol)

    def resaturate(self):
        chimera.viewer.background = self._old_background
        for mol in chimera.openModels.list(modelTypes=[chimera.Molecule]):
            mol.color = mol._old_color
            del mol._old_color
            for a in mol.atoms:
                a.color = a._old_color
                del a._old_color
            for r in mol.residues:
                r.ribbonColor, r.fillColor = r._old_colors
                del r._old_colors
    
    # Event handlers
    def on_focus_in(self, event):
        self.desaturate()

    def on_focus_out(self, event):
        self.resaturate()

    def on_selection_changed_proxy(self, *args):
        if not self._selecting:
            self.on_selection_changed(*args)

    def on_selection_changed(self, *args):
        current = self.current_selection()

        # Removed
        for obj, items in self.objects.items():
            if obj not in current:
                self.undo_depict(*items)
                for item in items:
                    item.delete()

        self.rebuild_tags()

        # Added
        for obj in current:
            if obj not in self._old_selection:
                self.add_item(obj=obj, insert=True)
        
        
        
        self._old_selection = current       

    @contextmanager
    def untriggered_selection(self):
        self._selecting = True
        yield
        self.after(100, lambda: setattr(self, '_selecting', False))



class ChimeraItem(SelectionItem):

    def specifier(self, obj):
        if isinstance(obj, chimera.Atom):
            return '#{}:{}.{}@{}'.format(obj.molecule.id, obj.residue.id.position, obj.residue.id.chainId.strip(), obj.name)
        elif isinstance(obj, chimera.Molecule):
            return '#{}'.format(obj.molecule)
        elif isinstance(obj, chimera.Residue):
            return '#{}:{}.{}'.format(obj.molecule.id, obj.id.position, obj.id.chainId)
        elif isinstance(obj, chimera.Bond):
            pass