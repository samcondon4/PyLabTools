""" This module implements the default interfaces for procedure Records.
"""
from pyqtgraph.parametertree import Parameter
import pyqtgraph.parametertree.parameterTypes as pTypes


class RecordUI(pTypes.GroupParameter):
    """ Group parameter type providing and basic interface to display the viewer and recorder names for a given record.
    """

    def __init__(self, records, **opts):
        children = [None for _ in records]
        i = 0
        for rec in records.values():
            viewer_param = Parameter.create(name="Viewer", type="str", value=str(rec.viewer), enabled=False)
            recorder_param = Parameter.create(name="Recorder", type="str", value=str(rec.recorder), enabled=False)
            children[i] = Parameter.create(name=rec.name, type='group', children=[viewer_param, recorder_param])
            i += 1

        opts['children'] = children
        opts['name'] = 'Records'
        opts['type'] = 'group'
        super().__init__(**opts)
