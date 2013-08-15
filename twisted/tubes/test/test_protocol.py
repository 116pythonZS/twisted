# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.tubes.protocol}.
"""

from twisted.tubes.test.util import StringEndpoint
from twisted.trial.unittest import TestCase
from twisted.tubes.protocol import factoryFromFlow
from twisted.tubes.tube import Pump
from twisted.tubes.tube import series
from twisted.python.failure import Failure
from twisted.tubes.test.util import FakeDrain
from twisted.tubes.test.util import FakeFount

class RememberingPump(Pump):
    """
    A pump that remembers what it receives.

    @ivar items: a list of objects that have been received.
    """

    def __init__(self):
        self.items = []
        self.wasStopped = False
        self.started()


    def received(self, item):
        self.items.append(item)


    def stopped(self, reason):
        self.wasStopped = True
        self.reason = reason



class FlowingAdapterTests(TestCase):
    """
    Tests for L{factoryFromFlow} and the drain/fount/factory adapters it
    constructs.
    """

    def setUp(self):
        """
        Sert up these tests.
        """
        self.endpoint = StringEndpoint()
        def flowFunction(fount, drain):
            self.adaptedDrain = drain
            self.adaptedFount = fount
        self.adaptedProtocol = self.successResultOf(
            self.endpoint.connect(factoryFromFlow(flowFunction))
        )

        self.pump = RememberingPump()
        self.tube = series(self.pump)


    def test_flowToSetsDrain(self):
        """
        L{_ProtocolFount.flowTo} will set the C{drain} attribute of the
        L{_ProtocolFount}.
        """
        self.adaptedFount.flowTo(self.tube)
        self.assertIdentical(self.adaptedFount.drain, self.tube)


    def test_flowToDeliversData(self):
        """
        L{_ProtocolFount.flowTo} will cause subsequent calls to
        L{_ProtocolFount.dataReceived} to invoke L{receive} on its drain.
        """
        self.adaptedFount.flowTo(self.tube)
        self.adaptedProtocol.dataReceived("some data")
        self.assertEquals(self.pump.items, ["some data"])


    def test_stopFlowStopsConnection(self):
        """
        L{_ProtocolFount.stopFlow} will close the underlying connection by
        calling C{loseConnection} on it.
        """
        self.adaptedFount.flowTo(self.tube)
        self.adaptedFount.stopFlow()
        self.assertEquals(self.adaptedProtocol.transport.disconnecting, True)
        # The connection has not been closed yet; we *asked* the flow to stop,
        # but it may not have done.
        self.assertEquals(self.pump.wasStopped, False)


    def test_loseConnectionSendsFlowStopped(self):
        """
        L{_ProtocolPlumbing.connectionLost} will notify its C{_fount}'s
        C{drain} that the flow has stopped, since the connection is now gone.
        """
        self.adaptedFount.flowTo(self.tube)
        class MyFunException(Exception):
            "An exception."
        f = Failure(MyFunException())
        self.adaptedProtocol.connectionLost(f)
        self.assertEquals(self.pump.wasStopped, True)
        self.assertIdentical(f, self.pump.reason)


    def test_flowingFromAttribute(self):
        """
        L{ProtocolAdapter.flowingFrom} will establish the appropriate L{IFount}
        to deliver L{pauseFlow} notifications to.
        """
        ff = FakeFount()
        self.adaptedDrain.flowingFrom(ff)
        self.assertIdentical(self.adaptedDrain.fount, ff)


    def test_pauseUnpause(self):
        """
        When an L{IFount} produces too much data for a L{_ProtocolDrain} to
        process, the L{push producer
        <twisted.internet.interfaces.IPushProducer>} associated with the
        L{_ProtocolDrain}'s transport will relay the L{pauseProducing}
        notification to that L{IFount}'s C{pauseFlow} method.
        """
        ff = FakeFount()
        # Sanity check.
        self.assertEquals(ff.flowIsPaused, False)
        self.adaptedDrain.flowingFrom(ff)
        # The connection is too full!  Back off!
        self.adaptedProtocol.transport.producer.pauseProducing()
        self.assertEquals(ff.flowIsPaused, True)
        # All clear, start writing again.
        self.adaptedProtocol.transport.producer.resumeProducing()
        self.assertEquals(ff.flowIsPaused, False)


    def test_stopProducing(self):
        """
        When C{stopProducing} is called on the L{push producer
        <twisted.internet.interfaces.IPushProducer>} associated with the
        L{_ProtocolDrain}'s transport, the L{_ProtocolDrain}'s C{fount}'s
        C{stopFlow} method will be invoked.
        """
        ff = FakeFount()
        ff.flowTo(self.adaptedDrain)
        self.adaptedDrain._transport.producer.stopProducing()
        self.assertEquals(ff.flowIsStopped, True)


    def test_flowingFrom(self):
        """
        L{_ProtocolFount.flowTo} returns the result of its argument's
        C{flowingFrom}.
        """
        another = FakeFount()
        class ReflowingFakeDrain(FakeDrain):
            def flowingFrom(self, fount):
                super(ReflowingFakeDrain, self).flowingFrom(fount)
                return another
        anotherOther = self.adaptedFount.flowTo(ReflowingFakeDrain())
        self.assertIdentical(another, anotherOther)


    def test_pureConsumerConnectionGetsShutDown(self):
        """
        When C{connectionLost} is called on a L{_ProtocolPlumbing} and it has
        an L{IFount} flowing to it (in other words, flowing to its
        L{_ProtocolDrain}), but no drain flowing I{from} it, the L{IFount}
        should have C{stopFlow} invoked on it so that it will no longer deliver
        to the now-dead transport.
        """
        ff = FakeFount()
        ff.flowTo(self.adaptedDrain)
        self.adaptedProtocol.connectionLost(
            Failure(Exception("it's a fair cop"))
        )
        self.assertEquals(ff.flowIsStopped, True)



