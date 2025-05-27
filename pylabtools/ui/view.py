""" This module implements the classes:

    - :class:`.ViewerWidget`
    - :class:`.LineViewerWidget`
    - :class:`.ImageViewerWidget`

    which serve to display the data buffered within the :class:`LineViewer <spherexlabtools.viewers.LineViewer>` and
    :class:`ImageViewer <spherexlabtools.viewers.ImageViewer>` classes.
"""
import datetime
import pyqtgraph as pg
from PyQt5 import QtWidgets


class ViewerWidget(QtWidgets.QWidget):
    """ Base QWidget object implementing a layout and a GraphicsLayoutWidget into which line plots and image displays
    are embedded.
    """

    def __init__(self, name=None, **kwargs):
        QtWidgets.QWidget.__init__(self, **kwargs)
        self.name = name
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        self.graphics_layout = pg.GraphicsLayoutWidget()
        self.layout.addWidget(self.graphics_layout)

    def update(self, *args, **kwargs):
        """ This is the main method of the ViewerWidgets which update the graphical elements
        of the display. Must be implemented in subclasses.
        """
        raise NotImplementedError('update() must be implemented in a ViewerWidget subclass!')


class LineViewerWidget(ViewerWidget):
    """ Embeds a line plot within the GraphicsLayoutWidget.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plot_item = self.graphics_layout.addPlot(row=0, col=0)
        self.legend_item = self.plot_item.addLegend()
        self.curve_items = {}

    def update(self, plot_dict):
        """ Updates the plot_item in the graphics layout with data transferred in the plot_dict.

        :param plot_dict: Dictionary of the following form: {'name of line': ([array of data], 'color of the line')}
        """
        new_curve_names = list(plot_dict.keys())

        # - remove any curves not in the set of new curves to plot - #
        cur_curve_names = list(self.curve_items.keys())
        for cur_curve_name in cur_curve_names:
            if cur_curve_name not in new_curve_names:
                curve_item = self.curve_items.pop(cur_curve_name)
                self.plot_item.removeItem(curve_item)

        # - update the curve items - #
        for curve_name in new_curve_names:
            data, pen_color = plot_dict[curve_name]
            if curve_name not in self.curve_items.keys():
                curve_item = pg.PlotCurveItem(name=curve_name, pen=pen_color)
                self.curve_items[curve_name] = curve_item
                self.plot_item.addItem(curve_item)
            self.curve_items[curve_name].setData(data)


class ImageViewerWidget(ViewerWidget):
    """ Embeds an image display into the GraphicsLayoutWidget.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.view = self.graphics_layout.addViewBox()
        self.view.setAspectLocked(True)
        self.img = pg.ImageItem(border='w')
        self.view.addItem(self.img)

    def update(self, img):
        """ Updates the image displayed in the image item display.

        :param img: 2-dimensional array of image data.
        """
        self.img.setImage(img['data'], **img['display_kwargs'])

