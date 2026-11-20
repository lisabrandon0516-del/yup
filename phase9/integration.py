from .workstation import CorporateHistoryWorkstation


def create(state, parent=None):
    page = CorporateHistoryWorkstation(parent)
    page.load(state)
    return page
