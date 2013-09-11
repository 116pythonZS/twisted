# -*- test-case-name: twisted.tubes.test.test_framing -*-
"""
Protocols to support framing.
"""

from zope.interface import implementer

from twisted.tubes.itube import ISwitchablePump
from twisted.tubes.tube import Pump
from twisted.protocols.basic import (
    LineOnlyReceiver, NetstringReceiver, Int8StringReceiver,
    Int16StringReceiver, Int32StringReceiver
)

class _Transporter(object):
    def __init__(self, deliver):
        self.deliver = deliver


    def write(self, data):
        self.deliver(data)


    def writeSequence(self, dati):
        for data in dati:
            self.deliver(data)



class _StringsToData(Pump):
    def __init__(self, stringReceiverClass, sendMethodName="sendString"):
        self._stringReceiver = stringReceiverClass()
        self.received = getattr(self._stringReceiver, sendMethodName)


    def started(self):
        self._stringReceiver.makeConnection(_Transporter(self.tube.deliver))



class _NotDisconnecting(object):
    """
    Enough of a transport to pretend to not be disconnecting.
    """
    disconnecting = False

    def loseConnection(self):
        """
        Hah.
        """



@implementer(ISwitchablePump)
class _DataToStrings(Pump):
    def __init__(self, stringReceiverClass,
                 receivedMethodName="stringReceived"):
        self._stringReceiver = stringReceiverClass()
        self._receivedMethodName = receivedMethodName
        self._stringReceiver.makeConnection(_NotDisconnecting())


    def started(self):
        self._ugh = []
        setattr(self._stringReceiver, self._receivedMethodName,
                lambda aaaugh: self._ugh.append(aaaugh))


    def received(self, string):
        self._stringReceiver.dataReceived(string)
        u, self._ugh = self._ugh, []
        return u


    def reassemble(self, datas):
        """
        convert these outputs into one of my inputs XXX describe better
        """
        delimiter = self._stringReceiver.delimiter
        return delimiter.join(list(datas) + [self._stringReceiver._buffer])



def stringsToNetstrings():
    return _StringsToData(NetstringReceiver)



def netstringsToStrings():
    return _DataToStrings(NetstringReceiver)



def linesToBytes():
    return _StringsToData(LineOnlyReceiver, "sendLine")



def bytesToLines():
    return _DataToStrings(LineOnlyReceiver, "lineReceived")



_packedPrefixProtocols = {
    8: Int8StringReceiver,
    16: Int16StringReceiver,
    32: Int32StringReceiver,
}

def packedPrefixToStrings(prefixBits):
    return _DataToStrings(_packedPrefixProtocols[prefixBits])



def stringsToPackedPrefix(prefixBits):
    return _StringsToData(_packedPrefixProtocols[prefixBits])
