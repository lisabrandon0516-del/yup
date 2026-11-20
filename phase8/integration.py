from .workstation import BoardObjectivesWorkstation


def create(state, parent=None):
    page = BoardObjectivesWorkstation(parent)
    page.load(state)
    return page
