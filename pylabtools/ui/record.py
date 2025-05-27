""" This module implements the basic interface class for procedure Records.
"""
from pyqtgraph.parametertree import Parameter
import pyqtgraph.parametertree.parameterTypes as pTypes


class RecordUI(pTypes.GroupParameter):
    """ Group parameter type providing a basic interface to display the viewer and recorder names for a given record.
    """

    def __init__(self, records, **opts):
        children = [None for _ in records]
        i = 0
        for rec in records.values():
            children[i] = Parameter.create(name=rec.name, type='group', children=[rec.viewer, rec.recorder])
            i += 1

        opts['children'] = children
        opts['name'] = 'Records'
        opts['type'] = 'group'
        super().__init__(**opts)
