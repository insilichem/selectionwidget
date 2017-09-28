#!/usr/bin/env python
# encoding: utf-8


from __future__ import print_function, division 
import chimera.extension


class SelectionExtension(chimera.extension.EMO):

    def name(self):
        return 'Selection Widget'

    def description(self):
        return 'An Excel-like selection dialog for UCSF Chimera'

    def categories(self):
        return ['InsiliChem']

    def icon(self):
        return

    def activate(self):
        self.module('gui').showUI()

chimera.extension.manager.registerExtension(SelectionExtension(__file__))
