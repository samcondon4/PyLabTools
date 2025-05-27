"""instrument:

    This module contains the classes :class:`.CompoundInstrument` and :class:`.InstrumentSuite`
"""
import logging
import importlib
import spherexlabtools.log as slt_log

log_name = f"{slt_log.LOGGER_NAME}.{__name__.split('.')[-1]}"
logger = logging.getLogger(log_name)


def instantiate_instrument(inst_dict, exp, dev_links=None, **instance_kwargs):
    """ Instantiate and return the appropriate PyMeasure Instrument class based on the inst_dict arguments.
    :param: inst_dict: dictionary corresponding to a single instrument. This dictionary should take the form seen at
                       :ref:`Instrument Dictionaries`
    """
    # check that the instrument dictionary contains valid arguments #
    assert "instance_name" in inst_dict, "Missing required argument 'instance_name' in instrument dictionary!"
    assert "manufacturer" in inst_dict, "Missing required argument 'manufacturer' in instrument dictionary!"
    assert "instrument" in inst_dict, "Missing required argument 'instrument' in instrument dictionary!"
    assert "resource_name" in inst_dict, "Missing required argument 'resource_name' in instrument dictionary!"
    assert not ("include_attrs" in inst_dict and "exclude_attrs" in inst_dict), \
        "Only one of {'include_attrs', 'exclude_attrs'} is allowed in an instrument dictionary!"

    manufacturer_string = inst_dict["manufacturer"]

    # first try to instantiate the instrument from the local instruments folder, then from spherexlabtools, then
    # from pymeasure.
    try:  # - local instruments module - #
        inst_mod = getattr(exp.instruments, manufacturer_string)
        inst_class = getattr(inst_mod, inst_dict["instrument"])
    except (AttributeError, ModuleNotFoundError):
        try:  # - spherexlabtools - #
            inst_mod = importlib.import_module(name="spherexlabtools.instruments.%s" % manufacturer_string)
            inst_class = getattr(inst_mod, inst_dict["instrument"])
        except (AttributeError, ModuleNotFoundError):
            try:  # - pymeasure - #
                inst_mod = importlib.import_module(name="pymeasure.instruments.%s" % manufacturer_string)
                inst_class = getattr(inst_mod, inst_dict["instrument"])
            except (AttributeError, ModuleNotFoundError):
                # - if the instrument driver class is still not found, then throw the error - #
                err_msg = "No instrument driver found for %s.%s" % (manufacturer_string, inst_dict["instrument"])
                logger.error(err_msg)
                raise AttributeError("No instrument driver found for %s.%s" % (manufacturer_string,
                                                                               inst_dict["instrument"]))

    logger.info(slt_log.INIT_MSG % inst_dict["instance_name"])
    # instantiate the instrument class with key-word arguments #
    if "kwargs" in inst_dict:
        instance_kwargs.update(inst_dict["kwargs"])
    try:
        rec_name = inst_dict["resource_name"]
        if type(dev_links) is dict and rec_name.__hash__ is not None and rec_name in dev_links.keys():
            rec_name = dev_links[rec_name]
        inst = inst_class(rec_name, **instance_kwargs)
    except Exception as e:
        logger.error("Error while instantiating {}.{}: \n {}".format(manufacturer_string, inst_dict["instrument"],
                                                                     e))
        raise e

    # set initial instrument parameters if any are given #
    if "params" in inst_dict:
        for param, param_val in inst_dict["params"].items():
            setattr(inst, param, param_val)
        logger.info(slt_log.CMPLT_MSG % f"{inst_dict['instance_name']} initialization")

    # - set the instrument name - #
    inst.name = inst_dict["instance_name"]
    return inst


class CompoundInstrument:
    """ Dynamic class that merges two or more Instruments into a single object.
    """

    _scope_char = "_"
    _init_complete = False

    def __init__(self, resource_name, name=None, instruments=None, **kwargs):
        self.rec_name = resource_name
        self.name = name
        self.instruments = instruments
        for instKey, instRument in self.instruments.items():
            attrs = [attr for attr in dir(instRument) if not attr.startswith("__")]
            for attr in attrs:
                attr_key = self._scope_char.join([instKey, attr])
                self.__dict__[attr_key] = None
        self._init_complete = True

    @staticmethod
    def get_inst_attr(self, name):
        scope_char = object.__getattribute__(self, "_scope_char")
        instruments = object.__getattribute__(self, "instruments")
        name_split = name.split(scope_char)
        if name_split[0] in instruments.keys():
            inst = instruments[name_split[0]]
            attr = scope_char.join(name_split[1:])
        else:
            inst = self
            attr = name

        return inst, attr

    def __getattribute__(self, name):
        if object.__getattribute__(self, "_init_complete"):
            get_inst_attr = object.__getattribute__(self, "get_inst_attr")
            inst, attr = get_inst_attr(self, name)
        else:
            inst = self
            attr = name
        return object.__getattribute__(inst, attr)

    def __setattr__(self, name, value):
        if object.__getattribute__(self, "_init_complete"):
            get_inst_attr = object.__getattribute__(self, "get_inst_attr")
            inst, attr = get_inst_attr(self, name)
        else:
            inst = self
            attr = name
        object.__setattr__(inst, attr, value)


class InstrumentSuite:
    """ Top-level instrument object to encapsulate all instruments within an experiment.
    """

    def __init__(self, inst_cfg, exp, dev_links=None):
        for inst in inst_cfg:
            # - normal instrument - #
            if "sub_instruments" not in inst:
                self.__dict__[inst["instance_name"]] = instantiate_instrument(inst, exp, dev_links=dev_links)

            # - compound instrument with a defined class - #
            elif "manufacturer" in inst and "instrument" in inst:
                instruments = {
                    cfg["instance_name"]: instantiate_instrument(cfg, exp, dev_links=dev_links) for
                    cfg in inst["sub_instruments"]
                }
                self.__dict__[inst["instance_name"]] = instantiate_instrument(inst, exp, dev_links=dev_links,
                                                                              instruments=instruments)
            # - compound instrument w/ no defined class - #
            else:
                instruments = {
                    cfg["instance_name"]: instantiate_instrument(cfg, exp, dev_links=dev_links) for
                    cfg in inst["sub_instruments"]
                }
                self.__dict__[inst["instance_name"]] = CompoundInstrument(inst["resource_name"],
                                                                          name=inst["instance_name"],
                                                                          instruments=instruments)
