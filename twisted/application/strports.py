# -*- test-case-name: twisted.test.test_strports -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Construct listening port services from a simple string description.

@see: L{twisted.internet.endpoints.serverFromString}
@see: L{twisted.internet.endpoints.clientFromString}
"""

import warnings

from twisted.internet import endpoints
from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version
from twisted.application.internet import StreamServerEndpointService



def parse(description, factory, default='tcp', quoting=False):
    """
    This function is deprecated as of Twisted 10.2.

    @param description: The description of the listening port, in the syntax
        described by L{twisted.internet.endpoints.serverFromString}.
    @type description: C{str}

    @param factory: The protocol factory which will build protocols for
        connections to this service.
    @type factory: L{twisted.internet.interfaces.IProtocolFactory}

    @param default: Do not use this parameter. It has been deprecated since
        Twisted 10.2.0.
    @type default: C{str} or C{None}

    @param quoting: Whether to allow quoting in the description string or not.
    @type quoting: C{bool}

    @return: a 3-tuple of (plugin or name, arguments, keyword arguments)

    @see: L{twisted.internet.endpoints.serverFromString}
    """
    return endpoints._parseServer(description, factory, default, quoting)

deprecatedModuleAttribute(
    Version("Twisted", 10, 2, 0),
    "in favor of twisted.internet.endpoints.serverFromString",
    __name__, "parse")



_DEFAULT = object()

def service(description, factory, default=_DEFAULT, quoting=False,
            reactor=None):
    """
    Return the service corresponding to a description.

    @param description: The description of the listening port, in the syntax
        described by L{twisted.internet.endpoints.serverFromString}.
    @type description: C{str}

    @param factory: The protocol factory which will build protocols for
        connections to this service.
    @type factory: L{twisted.internet.interfaces.IProtocolFactory}

    @param default: Do not use this parameter. It has been deprecated since
        Twisted 10.2.0.
    @type default: C{str} or C{None}

    @param quoting: Whether to allow quoting in the description string or not.
    @type quoting: C{bool}

    @param reactor: The server endpoint will be constructed with this reactor.
    @type reactor: L{twisted.internet.interfaces.IReactorCore} or C{None}

    @return: the service corresponding to a description of a reliable
        stream server.
    @rtype: C{twisted.application.service.IService}

    @see: L{twisted.internet.endpoints.serverFromString}
    """
    if reactor is None:
        from twisted.internet import reactor
    if default is _DEFAULT:
        default = None
    else:
        message = "The 'default' parameter was deprecated in Twisted 10.2.0."
        if default is not None:
            message += (
                "  Use qualified endpoint descriptions; for example, "
                "'tcp:%s'." % (description,))
        warnings.warn(
            message=message, category=DeprecationWarning, stacklevel=2)
    svc = StreamServerEndpointService(
        endpoints._serverFromStringLegacy(reactor, description, default,
            quoting),
        factory)
    svc._raiseSynchronously = True
    return svc



def listen(description, factory, default=None, quoting=False):
    """
    Listen on a port corresponding to a description

    @param description: The description of the listening port, in the syntax
        described by L{twisted.internet.endpoints.serverFromString}.
    @type description: C{str}

    @param factory: The protocol factory which will build protocols for
        connections to this service.
    @type factory: L{twisted.internet.interfaces.IProtocolFactory}

    @param default: Do not use this parameter. It has been deprecated since
        Twisted 10.2.0.
    @type default: C{str} or C{None}

    @param quoting: Whether to allow quoting in the description string or not.
    @type quoting: C{bool}

    @return: the port corresponding to a description of a reliable
    virtual circuit server.
    @rtype: C{twisted.internet.interfaces.IListeningPort}

    See the documentation of the C{parse} function for description
    of the semantics of the arguments.
    """
    from twisted.internet import reactor
    name, args, kw = parse(description, factory, default, quoting)
    return getattr(reactor, 'listen'+name)(*args, **kw)



__all__ = ['parse', 'service', 'listen']
