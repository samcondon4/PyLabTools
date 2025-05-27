""" This module implements a set of basic helper functions for user interface configuration.

Sam Condon, 2022-06-26
"""

from PyQt5 import QtWidgets, QtGui
from pyqtgraph.parametertree import Parameter


class StackedHelper:
    """ This class implements helpers for use with a QStackedWidget. It automatically configures the selector
        QComboBox to switch between widgets in the stack.
    """

    def __init__(self):
        """ Initialize a stacked widget helper.
        """
        self.stack = QtWidgets.QStackedWidget()
        self.stacked_selector_dict = {}

    def configure_stack(self, stack_widgets, stack_title, stack_selector):

        # ------------ configure fonts ------------- #
        title_font = QtGui.QFont()
        title_font.setFamily("Ubuntu")
        title_font.setPointSize(12)
        title_font.setBold(True)

        selector_font = QtGui.QFont()
        selector_font.setFamily("Ubuntu")
        selector_font.setPointSize(9)
        selector_font.setBold(False)

        for widget in stack_widgets:
            # - configure labels - #
            title_label = QtWidgets.QLabel()
            title_label.setText(stack_title)
            title_label.setFont(title_font)
            select_label = QtWidgets.QLabel()
            select_label.setText(stack_selector)
            select_label.setFont(selector_font)

            # - create the stack widget and layout - #
            stack_widget = QtWidgets.QWidget()
            stack_widget.setWindowTitle(widget.name)
            layout = QtWidgets.QGridLayout()
            stack_widget.setLayout(layout)

            # - add title and selector strings to the layout - #
            layout.addWidget(title_label)
            layout.addWidget(select_label)

            # - create the selector and add it to the layout - #
            selector = QtWidgets.QComboBox()
            for w in stack_widgets:
                selector.addItem(w.name)
            selector.currentIndexChanged.connect(self._on_stacked_widget_switch)
            layout.addWidget(selector)

            # - finally, add the stack widget to the layout and the final top widget to the stack - #
            layout.addWidget(widget)
            self.stack.addWidget(stack_widget)

            self.stacked_selector_dict[widget.name] = selector

    def _on_stacked_widget_switch(self):
        """ Signal to switch between widgets on the stack.
        """
        cur_window = self.stack.currentWidget().windowTitle()
        new_index = self.stacked_selector_dict[cur_window].currentIndex()
        self.stack.setCurrentIndex(new_index)
        new_window = self.stack.currentWidget().windowTitle()
        self.stacked_selector_dict[new_window].setCurrentIndex(new_index)


def get_object_parameters(obj):
    """ Return all of the pyqtgraph Parameter objects within the passed in object.

    :param obj: Object within which parameters are present.
    :return: List of pyqtgraph parameter objects.
    """
    params = []
    for attr_str in dir(obj):
        attr = getattr(obj, attr_str)
        if isinstance(attr, Parameter):
            params.append(attr)

    return params

