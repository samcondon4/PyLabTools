""" Module supporting dynamic loading of class instances. Implements the functions:

        :func:`.load_objects_from_cfg_list`
"""
import logging


logger = logging.getLogger(__name__)


class LoaderError(Exception):
    """ Exception raised when a class definition for an instance cannot be found.
    """
    pass


def load_objects_from_cfg_list(search_order, exp, cfg_list, **kwargs):
    """ Load a set of object instances from a list of configs with a specific module search order.

    :param search_order: List of module objects to search for class definitions.
    :param cfg_list: List of instance configuration dictionaries. These dictionaries must have at least
                     an 'instance_name' and 'type' key-value pair.
    :param exp: Experiment object to pass to class instantiation.
    :param cfg_list: String name of the exp_pkg attribute to retrieve the configuration list from.
    """
    objects = {}
    og_kwargs = kwargs
    for cfg in cfg_list:
        name = cfg["instance_name"]
        typ = cfg["type"]
        passed_kwargs = og_kwargs.copy()
        if "kwargs" in cfg.keys():
            passed_kwargs.update(cfg["kwargs"])
        inst_class = None
        for mod in search_order:
            try:
                inst_class = getattr(mod, typ)
            except AttributeError:
                pass
            else:
                logger.info("Initializing %s as %s" % (cfg["instance_name"], inst_class))
                try:
                    objects[name] = inst_class(cfg, exp=exp, **passed_kwargs)
                except Exception as e:
                    logger.error("Error while initializing {} of type {}! {}({})".format(name, typ, type(e), e))
                    raise e

        # if all modules searched and class def not found, raise and log error.
        if inst_class is None:
            err_msg = "Could not find type %s for instance %s" % (cfg["type"], cfg["instance_name"])
            logger.error(err_msg)
            raise LoaderError(err_msg)

        if "params" in cfg.keys():
            for pKey, pVal in cfg["params"].items():
                setattr(objects[name], pKey, pVal)

    return objects

