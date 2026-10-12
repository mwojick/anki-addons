from collections.abc import Sequence

from aqt import mw
from aqt.qt import *
from aqt import gui_hooks
from aqt.browser import Browser
from anki.notes import Note
from anki.decks import DeckId
from .ui.config import ConfigDialog
from .model.config import AddonConfig
from anki.collection import AddNoteRequest, Collection, OpChanges, OpChangesWithCount

config = AddonConfig(__name__)
currentBrowsers: set[Browser] = set()


def openConfig():
    configDialog = ConfigDialog(config)
    configDialog.exec()


def browser_init(browser: Browser):
    global currentBrowsers
    currentBrowsers.add(browser)


def setup_hooks():
    # TODO Restore original functions after user disables the addon
    if not hasattr(Collection, "_add_note"):
        Collection._add_note = Collection.add_note
    Collection.add_note = on_add_note
    if not hasattr(Collection, "_add_notes"):
        Collection._add_notes = Collection.add_notes
    Collection.add_notes = on_add_notes


def on_add_note(self: Collection, note: Note, deck_id: DeckId) -> OpChangesWithCount:
    ret: OpChangesWithCount = Collection._add_note(self, note, deck_id)
    mw.taskman.run_on_main(lambda: new_notes([note]))
    return ret


def on_add_notes(self: Collection, requests: Sequence[AddNoteRequest]) -> OpChanges:
    ret: OpChanges = Collection._add_notes(self, requests)
    notes = [request.note for request in requests]
    if notes:
        mw.taskman.run_on_main(lambda: new_notes(notes))
    return ret


def new_notes(notes: Sequence[Note]):
    global currentBrowsers

    deletedBrowsers: set[Browser] = set()

    for currentBrowser in currentBrowsers:
        if currentBrowser is None or sip.isdeleted(currentBrowser):
            deletedBrowsers.add(currentBrowser)
            continue

        if config.getAutoRefresh():
            currentBrowser.search()

        if config.getAutoSelect():
            # Select the last new note that is visible in the browser's current search
            for note in reversed(notes):
                cards = note.card_ids()
                if (
                    len(cards) > 0
                    and currentBrowser.table._model.get_card_row(cards[0]) is not None
                ):
                    currentBrowser.table.select_single_card(cards[0])
                    break

    currentBrowsers = currentBrowsers.difference(deletedBrowsers)


mw.addonManager.setConfigAction(__name__, openConfig)

gui_hooks.browser_menus_did_init.append(browser_init)
setup_hooks()
