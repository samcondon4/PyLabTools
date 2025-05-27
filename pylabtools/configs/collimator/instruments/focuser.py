""" This module implements the collimator focuser drive as a CompoundInstrument of an absolute gauge with
a linear stage drive.
"""

from spherexlabtools.instruments import CompoundInstrument


class Focuser(CompoundInstrument):

    def __init__(self, rec_name, gauge_name=None, stage_name=None,  retries=2, **kwargs):
        self.gauge_name = gauge_name if gauge_name is not None else "gauge"
        self.stage_name = stage_name if stage_name is not None else "fstage"
        self.retries = retries
        super().__init__(rec_name, **kwargs)
        self.absolute_to_steps = getattr(self, '_'.join([self.stage_name, 'absolute_to_steps']))

    @property
    def absolute_position(self):
        return self.gauge_position

    @absolute_position.setter
    def absolute_position(self, value):

        for i in range(self.retries):
            abs_pos = self.absolute_position
            delta = value - abs_pos
            steps = self.absolute_to_steps(delta)
            self.fstage_step_position += steps
            self.fstage_wait_for_completion()
