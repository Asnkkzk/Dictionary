"""Persistent appearance palettes for all dictionary windows."""
import tkinter as tk
from . import config

def palette():
    settings = config.get().get('appearance', {})
    light = settings.get('mode', 'dark') == 'light'
    bg = settings.get('background') or ('#edf2f7' if light else '#2b2b2e')
    return {'#2b2b2e': bg, '#232327': '#ffffff' if light else '#232327',
            '#f0f0f0': '#172033' if light else '#f0f0f0',
            '#9e9ea7': '#596579' if light else '#9e9ea7',
            '#3a3a3f': '#dde5ef' if light else '#3a3a3f',
            '#7cc6fe': '#1467ad' if light else '#7cc6fe',
            '#f8b26a': '#99500b' if light else '#f8b26a',
            '#5a2a2a': '#ffe0e0' if light else '#5a2a2a',
            '#ffb3b3': '#9f2424' if light else '#ffb3b3'}

def apply(widget):
    colors = palette()
    def visit(w):
        originals = getattr(w, '_theme_originals', {})
        for option in ('background', 'foreground', 'insertbackground', 'activebackground', 'activeforeground'):
            try:
                current = str(w.cget(option))
                old = originals.get(option)
                source = old[0] if old and current == old[1] else current
                target = colors.get(source, source)
                w.configure(**{option: target})
                originals[option] = (source, target)
            except tk.TclError:
                pass
        w._theme_originals = originals
        if isinstance(w, tk.Text):
            for tag, color in [('title', colors['#f0f0f0']), ('phonetic', colors['#9e9ea7']), ('translation', colors['#7cc6fe']), ('pos', colors['#f8b26a']), ('def', colors['#f0f0f0']), ('example', colors['#9e9ea7']), ('meta', colors['#9e9ea7'])]:
                w.tag_configure(tag, foreground=color)
        for child in w.winfo_children():
            visit(child)
    visit(widget)
