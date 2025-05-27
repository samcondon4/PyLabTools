""" This module implements the sequencer ui element.
"""
import os

import numpy as np
from PyQt5 import QtCore
from collections.abc import Iterable
import pyqtgraph.parametertree.parameterTypes as pTypes
from pyqtgraph.parametertree import Parameter


class DuplicateParameterError(Exception):
    pass


class SequenceGroup(pTypes.GroupParameter):
    """ Expandable GroupParameter implementing the sequence tree.
    """

    level_identifier = ": "

    def __init__(self, params, **opts):
        opts["name"] = "Sequence"
        opts["type"] = "group"
        opts["addText"] = "Add"
        opts["addList"] = [p["name"] for p in params]
        self.level = Parameter.create(name="Level", type="str", value="x")
        self.remove = Parameter.create(name="Remove", type="action")
        self.base_children = [self.level, self.remove]
        self.base_children_len = len(self.base_children)
        opts["children"] = self.base_children
        pTypes.GroupParameter.__init__(self, **opts)

        # connect buttons to methods #
        self.remove.sigStateChanged.connect(self.remove_child)

    def addNew(self, typ=None, level=None, val=""):
        """ Add a child to the sequence tree.
        """
        level = level if level is not None else self.level.value().split(".")
        children = self.children()
        child = self
        insert_pos = len(children) - len(self.base_children)
        insert_level = len(children) - len(self.base_children)
        for lvl in level:
            if lvl == "x":
                child.insertChild(insert_pos, dict(name=str(insert_level) + SequenceGroup.level_identifier + typ,
                                                   type="str", value=val, removeable=True))
            else:
                child = children[int(lvl)]
                children = child.children()
                insert_pos = len(children)
                insert_level = len(children)

    def remove_child(self):
        """ Remove a child at the specified level from the sequence tree.
        """

        level = self.level.value().split(".")
        children = self.children()
        child = self
        for lvl in level:
            child = children[int(lvl)]
            children = child.children()

        # get the current child parent #
        parent = child.parent()

        # remove specified child #
        if child not in self.base_children:
            parent.removeChild(child)

        # rename children #
        children = parent.children()
        for i in range(len(children)):
            child = children[i]
            if child not in self.base_children:
                name = child.name().split(":")[-1].strip()
                child.setName(str(i) + SequenceGroup.level_identifier + name)

    def get_node_str(self, node_dict, string, i):
        """ Get a readable string for a single node, recursively.
        """
        append_str = ""
        for param, val in node_dict.items():
            string += i * "\t" + f"{param}: {val[0]}\n"
            if len(val[1].items()) > 0:
                string = self.get_node_str(val[1], string, i + 1)
        return string

    def get_readable(self):
        """ Get a human readable string representation of the sequence dictionary.
        """
        seq_dict = self.getValues()
        seq_str = ""
        for param, val in seq_dict.items():
            if param not in ["Level", "Remove"]:
                seq_str += f"{param}: {val[0]}\n"
                seq_str = self.get_node_str(val[1], seq_str, 1)
        return seq_str


class SequenceUI(pTypes.GroupParameter):
    """ GroupParameter type wrapping the :class:`.SequenceGroup`
    """

    new_sequence = QtCore.pyqtSignal(object, object)
    pause_proc_sequence = QtCore.pyqtSignal()
    abort_proc_sequence = QtCore.pyqtSignal()

    def __init__(self, params, **opts):
        """ Initialize the sequencer.

        :param: params: Parameters to sequence through.
        """
        opts["name"] = "Procedure Sequencer"
        opts["type"] = "group"
        self.sequence_group = SequenceGroup(params)
        self.start_sequence = Parameter.create(name="Start Procedure Sequence", type="action")
        self.pause_sequence = Parameter.create(name="Pause Procedure Sequence", type="action")
        self.stop_sequence = Parameter.create(name="Abort Procedure Sequence", type="action")
        self.save_sequence = Parameter.create(name="Save Sequence", type="action", children=[
            {"name": "Save Path", "type": "file", "value": os.path.join(os.getcwd(), "sequence.txt")}
        ])
        self.load_sequence = Parameter.create(name="Load Sequence", type="action", children=[
            {"name": "Load Path", "type": "file", "value": os.path.join(os.getcwd(), 'sequence.txt')}
        ])
        self.base_children = [self.sequence_group, self.start_sequence, self.pause_sequence, self.stop_sequence,
                              self.save_sequence, self.load_sequence]
        opts["children"] = self.base_children
        pTypes.GroupParameter.__init__(self, **opts)

        # connect buttons to methods #
        self.start_sequence.sigStateChanged.connect(self.build_sequence)
        self.pause_sequence.sigActivated.connect(self.pause_proc_sequence.emit)
        self.stop_sequence.sigActivated.connect(self.abort_proc_sequence.emit)
        self.save_sequence.sigActivated.connect(self.write_sequence)
        self.load_sequence.sigActivated.connect(self.input_sequence)

    def build_sequence(self):
        """ Build a procedure sequence from the sequencer parameters.
        """
        sequence = []
        # get the sequence group children values and remove the buttons #
        seq_dict = self.sequence_group.getValues()
        seq_dict.pop("Level")
        seq_dict.pop("Remove")

        # build sequence parameters #
        for node in seq_dict.items():
            procs = [{}]
            procs = self.build_node_sequence(node, sequence, procs)
            sequence.extend(procs)

        # strip levels from each procedure dictionary key #
        for i in range(len(sequence)):
            proc_dict = sequence[i]
            new_dict = {key.split(SequenceGroup.level_identifier)[-1]: val for key, val in proc_dict.items()}
            sequence[i] = new_dict

        self.new_sequence.emit(seq_dict, sequence)

    def build_node_sequence(self, node, sequence, procs):
        """ Build procedure sequence for a single parameter tree node.
        """
        top_key = node[0]
        top_val = self.typecast(node[1][0])
        procs = self.update_procs_list(procs, top_key, top_val)
        children = node[1][1].items()
        for c in children:
            procs = self.build_node_sequence(c, sequence, procs)

        return procs

    def write_sequence(self):
        """ Save the current sequence out to a .txt file
        """
        save_path = self.save_sequence.child("Save Path").value()
        seq_group = self.sequence_group.get_readable()
        with open(save_path, "w") as f:
            f.write(seq_group)

    def input_sequence(self):
        """ Load an existing sequence .txt file.
        """
        load_path = self.load_sequence.child("Load Path").value()
        # clear the current sequence children #
        for child in self.sequence_group.children():
            if child not in self.sequence_group.base_children:
                self.sequence_group.removeChild(child)
        with open(load_path, "r") as f:
            top_level = -1
            sub_levels = []
            tabs = 0
            for line in f.readlines():
                if not line.startswith("\t"):
                    top_level += 1
                    level = [top_level]
                    sub_levels = []
                    tabs = 0
                else:
                    tab_split = line.split("\t")
                    new_tabs = len(tab_split) - 1
                    if new_tabs > tabs:
                        sub_levels.append(0)
                    elif new_tabs < tabs:
                        for i in range(tabs - new_tabs):
                            sub_levels.pop()
                    else:
                        sub_levels[new_tabs-1] += 1
                    level = [str(val) for val in [top_level] + sub_levels]
                    tabs = new_tabs
                level[-1] = "x"
                typ_val_split = line.split(":")
                typ = typ_val_split[1].strip()
                val = typ_val_split[2].strip()
                self.sequence_group.addNew(typ=typ, level=level, val=val)

    @staticmethod
    def update_procs_list(procs, key, val):
        """ Update list of procedures based on data values of the given node.
        """
        if issubclass(type(val), Iterable) and type(val) is not str:
            new_procs = []
            for proc in procs:
                proc_list = [{key: v} for v in val]
                for d in proc_list:
                    d.update(proc)
                new_procs.extend(proc_list)
        else:
            for p in procs:
                p.update({key: val})
            new_procs = procs

        return new_procs

    def typecast(self, val):
        """ Method to typecast an item value from its original string type to an iterable, or numeric
            type.

        :param: val: Original string to cast.
        """
        typecast = val
        sign = 1
        if val.startswith("-"):
            val = val[1:]
            sign = -1
        try:
            typecast = sign * float(val)
        except ValueError:
            if val.startswith("[") and val.endswith("]"):
                val_list = val[1:-1].split(",")
                for i in range(len(val_list)):
                    val_list[i] = self.typecast(val_list[i].strip())
                typecast = val_list
            elif "np" in val:
                np_array = eval(val)
                if type(np_array) is not np.ndarray:
                    raise TypeError("Only numpy arrays are allowed for numpy commands.")
                typecast = np_array

        return typecast

    def write_dict(self, dct, child):
        children = child.children()
        if len(children) > 0:
            for c in children:
                self.write_dict(dct, c)
        dct[child.name()] = child.value()


