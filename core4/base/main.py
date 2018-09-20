# -*- coding: utf-8 -*-

"""
This module features :class:`.CoreBase`, the base class to all core4 classes.
All classes inheriting from :class:`.CoreBase` provide the developer with the
following features:

* a :meth:`.qual_name` locates the class in the core4 runtime enrivonment. The
  :meth:`.qual_name` for example is used to address jobs, APIs, and widgets
  among others.

* a :attr:`.identifier` identifies the individual object instance of the class;
  this is None with :class:`.CoreBase` and extends into the job ``_id`` or the
  worker identifier for child classes.
"""

import inspect
import logging
import logging.handlers
import os
import re
import sys

import core4.config.main
import core4.logger
import core4.logger.filter
import core4.util
import core4.error
import core4.config.map

CORE4 = "core4"
PLUGIN = ["core4", "plugin"]


class CoreBase:
    """
    This is the base class to all core4 classes. :class:`CoreBase` ships with

    * access to configuration keys/values including plugin based extra
      configuration settings, use :attr:`.config`, here.
    * standard logging facilities, use :attr:`.logger`, here.
    * a distinct qual_name based on module path and class name with
      :meth:`.qual_name`.
    * a unique object identifier, i.e. the job id, the request id or the name
      of the worker with :attr:`.identifier`.

    .. note:: Please note that :class:`.CoreBase` replicates the identifier of
              the class in which scope the object is created. If an object _A_
              derived from  :class:`.CoreBase` has an :attr:`.identifer` not
              ``None`` and creates another object _B_ which inherits from
              :class:`.CoreBase`, too, then the :attr:`.identifier` is passed
              from object _A_ to object _B_.
    """
    _qual_name = None
    plugin = None
    identifier = None
    unwind_keys = ["log_level"]

    def __init__(self):

        # set identifier
        frame = inspect.currentframe().f_back.f_locals
        for n, v in frame.items():
            if hasattr(v, "qual_name"):
                ident = getattr(v, "identifier", None)
                if not isinstance(ident, property):
                    if ident is not None:
                        self.identifier = ident
        self._last_progress = None
        self._set_plugin()
        self._open_config()
        self._open_logging()

    def _set_plugin(self):
        self.plugin = self.__class__.__module__.split('.')[0]
        # the following is a hack
        if self.plugin == '__main__':  # pragma: no cover
            dirname = os.path.dirname(sys.argv[0]).split('/')
            pathname = [os.path.splitext(sys.argv[0].split('/')[-1])[0]]
            while dirname:
                init_file = "/".join(dirname + ['__init__.py'])
                pathname.append(dirname.pop(-1))
                if os.path.exists(init_file):
                    with open(init_file, 'r') as fh:
                        body = fh.read()
                        if re.match(
                                r'.*\_\_project\_\_\s*'
                                r'\=\s*[\"\']{}[\"\'].*'.format(
                                    CORE4), body, re.DOTALL):
                            self.__class__._qual_name = ".".join(
                                list(reversed(pathname))
                                + [self.__class__.__name__])
                            self.plugin = pathname.pop(-1)
                            break

    def __repr__(self):
        return "{}()".format(self.qual_name())

    @classmethod
    def qual_name(cls, short=True):
        """
        Returns the distinct ``qual_name``, the fully qualified module and
        class name. With ``short=False`` the prefix ``core4.plugin`` is
        put in front of all plugin classes.

        :param short: defaults to ``False``
        :return: qual_name string
        """
        if cls._qual_name:  # pragma: no cover (see test_base.test_main)
            return cls._qual_name
        plugin = cls.__module__.split('.')[0]
        if plugin != CORE4 and not short:
            return '.'.join(PLUGIN + [cls.__module__, cls.__name__])
        return '.'.join([cls.__module__, cls.__name__])

    def plugin_config(self):
        """
        Returns the expected path and file name of the plugin configuration.
        Note that this method does not verify that the file actually exists.

        :return: str
        """
        module = sys.modules.get(self.plugin)
        if module:
            if hasattr(module, "__project__"):
                if module.__project__ == CORE4:
                    return os.path.join(
                        os.path.dirname(module.__file__),
                        self.plugin + core4.config.main.CONFIG_EXTENSION)
        return None

    def _open_config(self):
        # internal method to open and attach core4 cascading configuration
        kwargs = {}
        plugin_config = self.plugin_config()
        if plugin_config and os.path.exists(plugin_config):
            kwargs["plugin_config"] = (self.plugin, plugin_config)
        kwargs["extra_dict"] = self._add_extra_config()
        self.config = core4.config.CoreConfig(**kwargs)
        self._add_extra_config()
        self._unwind_config()

    def _add_extra_config(self):
        extra_config = {}
        pos = extra_config
        for p in self.qual_name(short=True).split("."):
            pos[p] = {}
            pos = pos[p]
        self.class_config = pos
        pos["log_level"] = None
        return extra_config

    def _unwind_config(self):
        for k in self.config.base:
            if k in self.unwind_keys:
                if k in self.class_config:
                    if self.class_config[k] is not None:
                        self.__dict__[k] = self.class_config[k]
                        continue
                    self.__dict__[k] = self.config.base[k]

    def _open_logging(self):
        # internal method to open and attach core4 logging
        self.logger_name = self.qual_name(short=False)
        logger = logging.getLogger(self.logger_name)
        level = self.log_level
        logger.setLevel(getattr(logging, level))
        nh = logging.NullHandler()
        logger.addHandler(nh)
        f = core4.logger.filter.CoreLoggingFilter()
        logger.addFilter(f)
        # pass object reference into logging and enable lazy property access
        #   and late binding
        self.logger = core4.logger.CoreLoggingAdapter(logger, self)

    def log_progress(self, p, *args):
        """
        Internal method used to log progress. Overwrite this method to
        implement custom progress logging.

        :param p: current progress value (0.0 - 1.0)
        :param args: message and optional variables using Python format
                     operator
        """
        if args:
            args = list(args)
            fmt = " - {}".format(args.pop(0))
        else:
            fmt = ""
        self.logger.info('progress at %.0f%%' + fmt, p, *args)

    def progress(self, p, *args, inc=0.05):
        """
        Progress counter calling :meth:`.log_progress` to handle progress and
        message output. All progress outside bins defined by ``inc`` are
        reported only once and otherwise suppressed. This method reliable
        reports progress without creating too much noise in core4 logging
        targets.

        .. note:: Still you can reuse progress reporting. If the current
                  progress is below the last reported progress, then reporting
                  restarts.

        :param p: current progress value (0.0 - 1.0)
        :param args: message and optional variables using Python format
                     operator
        :param inc: progress bins, defaults to 0.05 (5%)
        """
        p_round = round(p / inc) * inc
        if self._last_progress is None or p_round != self._last_progress:
            self.log_progress(p_round * 100., *args)
            self._last_progress = p_round
