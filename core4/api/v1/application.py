#
# Copyright 2018 Plan.Net Business Intelligence GmbH & Co. KG
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
This module implements :class:`.CoreApiContainer` bundling multiple request
handlers under the same root endpoint. This class uses
:class:`.CoreApplication` derived from :class:`tornado.web.Application` and a
hierarchical routing mechanic to deliver these endpoints.

A blueprint for server definition and startup is::

    from core4.api.v1.application import CoreApiContainer
    from core4.api.v1.request.queue.job import JobHandler
    from core4.api.v1.tool.functool import serve

    class TestContainer(CoreApiContainer):
        root = "/test/api"
        rules = [
            (r'/job/?(.*)', JobHandler)
        ]


    if __name__ == '__main__':
        serve(TestContainer)


Please note that :meth:`.serve` can handle one or multiple
:class:`.CoreApiServer` objects with multiple endpoints and resources as in
the following example::

    serve(TestContainer, AnotherContainer)

Additionally this module features :class:`RootContainer`. This container is
attached to *each* :class:`.CoreApiContainer` and delivers core4 default
resource, i.e. ``/login``, ``/logout``, ``/profile``, ``/file``, ``/info``,
and the root endpoint ``/``. All these default endpoints are routed under a
dedicated core4 api endpoint (defaults to ``/core4/api/v1``).
"""

import hashlib
from pprint import pformat

import core4.const
import core4.error
import core4.util.node
import tornado.routing
import tornado.web
from core4.api.v1.request.default import DefaultHandler
from core4.api.v1.request.info import InfoHandler
from core4.api.v1.request.main import CoreBaseHandler
from core4.api.v1.request.standard.asset import CoreAssetHandler
from core4.api.v1.request.standard.login import LoginHandler
from core4.api.v1.request.standard.logout import LogoutHandler
from core4.api.v1.request.standard.profile import ProfileHandler
from core4.api.v1.request.standard.route import RouteHandler
from core4.api.v1.request.standard.setting import SettingHandler
from core4.api.v1.request.static import CoreStaticFileHandler
from core4.base.main import CoreBase

STATIC_PATTERN = "/(.*)$"


class CoreRoutingRule(tornado.routing.Rule):
    """
    Routing rule inherited from :class:`tornado.routing.Rule. Adds the
    rule attribute ``.route_id``  which is used by core4 to identify rules
    without a route_name.
    """

    def __init__(self, route_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.route_id = route_id


class CoreApiContainer(CoreBase):
    """
    :class:`CoreApiContainer` class is a container for a single or multiple
    :class:`.CoreRequestHandler` and is based on torando's class
    :class:`tornado.web.RequestHandler`. A container encapsulates endpoint
    resources under the same :attr:`.root` URL defined by the :attr:`.root`
    attribute.

    The default ``root`` is the project name.
    """

    #: if ``True`` then the application container is deployed with serve_all
    enabled = True
    #: root URL, defaults to the project name
    root = None
    #: list of tuples with route, request handler (i.e.
    #  :class:`.CoreRequestHandler` or class:`tornado.web.RequestHandler`
    #  derived class
    rules = []

    upwind = ["log_level", "enabled", "root"]

    def __init__(self, **kwargs):
        CoreBase.__init__(self)
        for attr in ("debug", "compress_response", "cookie_secret"):
            kwargs[attr] = kwargs.get(attr, self.config.api.setting[attr])
        kwargs["default_handler_class"] = DefaultHandler
        kwargs["default_handler_args"] = ()
        kwargs["log_function"] = self._log
        self._settings = kwargs
        self.started = None
        # upwind class properties from configuration
        for prop in ("enabled", "root"):
            if prop in self.class_config:
                if self.class_config[prop] is not None:
                    setattr(self, prop, self.class_config[prop])

    def _log(self, handler):
        # internal logging method
        if getattr(handler, "logger", None) is None:
            # regular logging
            logger = self.logger
            identifier = self.identifier
        else:
            # CoreRequestHandler logging
            logger = handler.logger
            identifier = handler.identifier
        if handler.get_status() < 400:
            meth = logger.info
        elif handler.get_status() < 500:
            meth = logger.warning
        else:
            meth = logger.error
        request_time = 1000.0 * handler.request.request_time()
        meth("[%d] [%s %s] in [%.2fms] by [%s] from [%s]",
             handler.get_status(), handler.request.method,
             handler.request.path, request_time, handler.current_user,
             self.identifier, extra={"identifier": identifier})

    def get_root(self, path=None):
        """
        Returns the container`s ``root`` URL or prefixes the passed relative
        path with the container's ``root``

        :param path: relative path (optional)
        :return: ``root`` or absolute path below ``root``
        """
        root = self.root
        if root is None:
            root = self.project
        if not root.startswith("/"):
            root = "/" + root
        if root.endswith("/"):
            root = root[:-1]
        if path:
            if not path.startswith("/"):
                path = "/" + path
            return root + path
        return root

    def iter_rule(self):
        """
        Returns a :class:`tornado.web.URLSpec` as specified by the container's
        :attr:`rules` attribute. This rule attribute can either be an
        ``URLSpec`` by itself or a tuple of ``pattern``, ``handler`` class,
        an optional ``kwargs`` to be passed to the handler and an optional
        rule ``name``.

        :return: yields :class:`tornado.web.URLSpec` objects
        """
        for ret in self.rules:
            if isinstance(ret, tornado.web.URLSpec):
                pattern = self.get_root(ret.regex.pattern)
                handler = ret.target
                kwargs = ret.kwargs
                name = ret.name
            else:
                ret = list(ret)
                pattern = self.get_root(ret.pop(0))
                handler = ret.pop(0)
                if not issubclass(handler, tornado.web.RequestHandler):
                    raise core4.error.Core4SetupError(
                        "expected subclass of RequestHandler, not [{}]".format(
                            type(handler)
                        )
                    )
                try:
                    kwargs = ret.pop(0)
                except IndexError:
                    kwargs = None
                try:
                    name = ret.pop(0)
                except IndexError:
                    name = None
            if issubclass(handler, CoreStaticFileHandler):
                yield tornado.web.URLSpec(
                    pattern=pattern + "/(.*)$",
                    handler=handler,
                    kwargs=kwargs,
                    name=name
                )
                yield tornado.web.URLSpec(
                    pattern=pattern + "(?:/(.*))?$",
                    handler=handler,
                    kwargs=kwargs,
                )
            else:
                yield tornado.web.URLSpec(
                    pattern=pattern,
                    handler=handler,
                    kwargs=kwargs,
                    name=name
                )

    def make_application(self):
        """
        Validates and pre-processes :class:`CoreApiContainer` rules and
        transfers a handler lookup dictionary to :class:`RootContainer` for
        reverse URL lookup.

        :return: :class:`.CoreApplication` instance
        """
        unique = set()
        rules = []
        for rule in self.iter_rule():
            routing = rule.regex.pattern
            cls = rule.target
            if rule.kwargs is None:
                kwargs = {}
            else:
                kwargs = rule.kwargs.copy()
            # md5 includes prefix and route
            sorted_kwargs = pformat(kwargs)
            hash_base = "{}:{}".format(cls.qual_name(), sorted_kwargs)
            md5_route = hashlib.md5(hash_base.encode("utf-8")).hexdigest()
            kwargs["_route_id"] = md5_route
            if routing not in unique:
                unique.add(routing)
                rules.append(
                    CoreRoutingRule(
                        md5_route,
                        tornado.routing.PathMatches(routing),
                        target=cls, target_kwargs=kwargs, name=rule.name))
                # lookup applies to core request handlers only
                if issubclass(cls, CoreBaseHandler):
                    self.logger.info(
                        "started [%s] on [%s] as [%s] with [%s]",
                        rule.target.qual_name(),
                        rule.regex.pattern,
                        rule.name or md5_route, kwargs)
            else:
                raise core4.error.Core4SetupError(
                    "route [%s] already exists" % routing)
        app = CoreApplication(rules, self, **self._settings)
        # transfer routes lookup with handler/routing md5 and app to container
        for rule in rules:
            if rule.route_id not in RootContainer.routes:
                RootContainer.routes[rule.route_id] = []
            RootContainer.routes[rule.route_id].append((app, self, rule))
        self.started = core4.util.node.now()
        return app


class CoreApplication(tornado.web.Application):
    """
    Represents a wrapper class around :class:`tornado.web.Application`. This
    wrapper extends applications' properties with a ``.container`` property
    referencing the :class:`.CoreApiContainer` object and delivers special
    processing for the *CARD* and *ENTER* handler requests.
    """

    def __init__(self, handlers, container, *args, **kwargs):
        super().__init__(handlers, *args, **kwargs)
        self.container = container
        self.identifier = container.identifier

    def find_handler(self, request, **kwargs):
        """
        Implements special handling for card page requests and landing page
        requests (*ENTER*).

        Card page requests are forwarded to the handler's
        :meth:`.CoreRequestHandler.card` method (``XCARD``). Enter landing
        page requests are forwarded to the handler's
        :meth:`.CoreRequestHandler.enter` method (``XENTER``).
        """

        def _find():
            parts = request.path.split("/")
            while parts[-1] == "":
                parts.pop()
            md5_route_id = parts.pop()
            return self.find_md5(md5_route_id)

        if request.path.startswith(core4.const.CARD_URL):
            (app, container, specs) = _find()
            request.method = core4.const.CARD_METHOD
            return self.get_handler_delegate(request, specs.target,
                                             specs.target_kwargs)
        elif request.path.startswith(core4.const.ENTER_URL):
            (app, container, specs) = _find()
            request.method = core4.const.ENTER_METHOD
            return self.get_handler_delegate(request, specs.target,
                                             specs.target_kwargs)
        return super().find_handler(request, **kwargs)

    def find_md5(self, route_id, all=False):
        """
        Find the passed ``route_id`` lookup built during the creation of
        application (:meth:`.make_application`). The ``route_id`` represents
        a MD5 checksum based on the ``qual_name`` of the handler and the
        parameters of the handler used during construction in
        :class:`.CoreApiContainer`. The combination of a ``qual_name`` and the
        custom parameters are considered *unique*.

        :param route_id: find the request handler based on
            :class:`.CoreRequestHandler` by the ``route_id`` MD5 digest.
        :param all: retrieve the first (``all is False``) or *all* handlers,
            defaults to ``False``
            :class:`.CoreRequestHandler` by the ``route_id`` MD5 digest.
        :return: tuple of (:class:`.Application`, :class:`.CoreApiContainer`,
            :class:`.CoreRoutingRule`)
        """
        route = RootContainer.routes.get(route_id, None)
        if route is None:
            return None
        if not all:
            return route[0]
        return route

    def handler_help(self, cls):
        """
        Delivers dict with help information about the passed
        :class:`.CoreRequestHandler` class

        :param cls: :class:`.CoreRequestHandler` class
        :return: dict as delivered by :meth:`.CoreApiInspectir.handler_info`
        """
        from core4.service.introspect.api import CoreApiInspector
        inspect = core4.service.introspect.api.CoreApiInspector()
        return inspect.handler_info(cls)


class RootContainer(CoreApiContainer):
    """
    This class is automatically attached to each server with :meth:`serve``
    or :meth:`serve_all` to deliver the following standard request handlers
    with core4:

    * ``/core4/api/login`` with :class:`.LoginHandler`
    * ``/core4/api/logout`` with :class:`.LogoutHandler`
    * ``/core4/api/profile`` with :class:`.ProfileHandler`
    * ``/core4/api/file`` for static file access with :class:`FileHandler`
    * ``/core4/api/info`` with :class:`.RouteHandler` and :class:`.InfoHandler`
    * ``/core4/api/setting`` with :class:`.SettingHandler`
    * ``/`` for ``favicon.ico`` delivery with :class:`.CoreStaticFileHandler`
    """
    root = ""
    rules = [
        (core4.const.CORE4_API + r"/login", LoginHandler),
        (core4.const.CORE4_API + r"/logout", LogoutHandler),
        (core4.const.CORE4_API + r"/profile", ProfileHandler),
        (core4.const.CORE4_API + r"/file/(.*)", CoreAssetHandler),
        (core4.const.CORE4_API + r'/info', RouteHandler),
        (core4.const.CORE4_API + r'/info/(.+)', InfoHandler),
        (core4.const.CORE4_API + r'/setting', SettingHandler),
        (core4.const.CORE4_API + r'/setting/(.*)', SettingHandler),
        (r'', CoreStaticFileHandler, {
            "path": "./request/_static",
            "protected": False,
            "title": "core4 landing page",
        })
    ]
    routes = {}
