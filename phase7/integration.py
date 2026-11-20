from .workstation import DelegationWorkstation


def create(state, parent=None):
    page = DelegationWorkstation(parent)
    page.load(state)
    return page
