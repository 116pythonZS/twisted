# -*- test-case-name: twisted.threads.test.test_team -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of a L{Team} of workers; a thread-pool that can allocate work to
workers.
"""

from collections import deque
from zope.interface import implementer

from . import IWorker
from ._convenience import Quit



class Statistics(object):
    """
    Statistics about a L{Team}'s current activity.

    @ivar idleWorkerCount: The number of idle workers.
    @type idleWorkerCount: L{int}

    @ivar busyWorkerCount: The number of busy workers.
    @type busyWorkerCount: L{int}

    @ivar backloggedWorkCount: The number of work items passed to L{Team.do}
        which have not yet been sent to a worker to be performed because not
        enough workers are available.
    @type backloggedWorkCount: L{int}
    """

    def __init__(self, idleWorkerCount, busyWorkerCount,
                 backloggedWorkCount):
        self.idleWorkerCount = idleWorkerCount
        self.busyWorkerCount = busyWorkerCount
        self.backloggedWorkCount = backloggedWorkCount



@implementer(IWorker)
class Team(object):
    """
    A composite L{IWorker} implementation.
    """

    def __init__(self, coordinator, createWorker, logException):
        """
        @param coordinator: an L{IWorker} which will coordinate access to
            resources on this L{Team}; that is to say, an L{IWorker} whose
            C{do} method ensures that its given work will be executed in a
            mutually exclusive context, not in parallel with other work
            enqueued by C{do} (although possibly in parallel with the caller).

        @param createWorker: A 0-argument callable that will create an
            L{IWorker} to perform work.

        @param logException: A 0-argument callable called in an exception
            context when the work passed to C{do} raises an exception.
        """
        self._quit = Quit()
        self._coordinator = coordinator
        self._createWorker = createWorker
        self._logException = logException

        # Don't touch these except from the coordinator.
        self._idle = set()
        self._busyCount = 0
        self._pending = deque()
        self._coordinatorQuit = False
        self._toShrink = 0


    def statistics(self):
        """
        Gather information on the current status of this L{Team}.

        @return: a L{Statistics} describing the current state of this L{Team}.
        """
        return Statistics(len(self._idle), self._busyCount, len(self._pending))


    def grow(self, n):
        """
        Increase the the number of idle workers by C{n}.

        @param n: The number of new idle workers to create.
        @type n: L{int}
        """
        self._quit.check()
        @self._coordinator.do
        def createOneWorker():
            for x in range(n):
                worker = self._createWorker()
                if worker is None:
                    return
                self._recycleWorker(worker)


    def shrink(self, n=None):
        """
        Decrease the number of idle workers by C{n}.

        @param n: The number of idle workers to shut down, or C{None} (or
            unspecified) to shut down all workers.
        @type n: L{int} or L{types.NoneType}
        """
        self._quit.check()
        self._coordinator.do(lambda: self._quitIdlers(n))


    def _quitIdlers(self, n=None):
        """
        The implmentation of C{shrink}, performed by the coordinator worker.

        @param n: see L{Team.shrink}
        """
        if n is None:
            n = len(self._idle) + self._busyCount
        for x in range(n):
            if self._idle:
                self._idle.pop().quit()
            else:
                self._toShrink += 1
        # TODO: the following expression is insufficiently tested.
        if ((not self._coordinatorQuit) and (self._busyCount == 0) and
            (len(self._pending) == 0) and (self._quit.isSet)):
            self._coordinatorQuit = True
            self._coordinator.quit()


    def do(self, task):
        """
        Perform some work in a worker created by C{createWorker}.

        @param task: the callable to run
        """
        self._quit.check()
        self._coordinator.do(lambda: self._coordinateThisTask(task))


    def _coordinateThisTask(self, task):
        """
        Select a worker to dispatch to, either an idle one or a new one, and
        perform it.

        This method should run on the coordinator worker.

        @param task: the task to dispatch
        @type task: 0-argument callable
        """
        worker = (self._idle.pop() if self._idle
                  else self._createWorker())
        if worker is None:
            # The createWorker method may return None if we're out of resources
            # to create workers.
            self._pending.append(task)
            return
        self._busyCount += 1
        @worker.do
        def doWork():
            try:
                task()
            except:
                self._logException()

            @self._coordinator.do
            def idleAndPending():
                self._busyCount -= 1
                self._recycleWorker(worker)


    def _recycleWorker(self, worker):
        """
        Called only from coordinator.

        Recycle the given worker into the idle pool.

        @param worker: a worker created by C{createWorker} and now idle.
        @type worker: L{IWorker}
        """
        self._idle.add(worker)
        if self._pending:
            # Re-try the first enqueued thing.
            # (Explicitly do _not_ honor _quit.)
            self._coordinateThisTask(self._pending.popleft())
        elif self._quit.isSet:
            self._quitIdlers()
        elif self._toShrink > 0:
            self._toShrink -= 1
            self._idle.remove(worker)
            worker.quit()


    def quit(self):
        """
        Stop doing work and shut down all idle workers.
        """
        self._quit.set()
        # In case all the workers are idle when we do this.
        self._coordinator.do(self._quitIdlers)


    @classmethod
    def withLimit(cls, currentLimit, threadFactory=None,
                  reactor=None):
        """
        Construct a L{Team} that spawns threads, with the given limiting
        function.

        @param withLimit: a callable that returns the current limit on the
            number of workers that the returned L{Team} should create; if it
            already has more workers than that value, no new workers will be
            created.
        @type withLimit: 0-argument callable returning L{int}

        @param reactor: If passed, the L{IReactorFromThreads} / L{IReactorCore}
            to be used to coordinate actions on the L{Team} itself.  Otherwise,
            a L{LockWorker} will be used.
        """
        try:
            from Queue import Queue
        except ImportError:
            from queue import Queue

        from ._threadworker import ThreadWorker

        from twisted.python.log import err
        if threadFactory is None:
            from threading import Thread as threadFactory
        def startThread(target):
            return threadFactory(target=target).start()
        def limitedWorkerCreator():
            stats = team.statistics()
            if stats.busyWorkerCount + stats.idleWorkerCount >= currentLimit():
                return None
            return ThreadWorker(startThread, Queue())

        if reactor is None:
            from threading import Lock, local as LocalStorage
            from ._threadworker import LockWorker
            coordinator = LockWorker(Lock(), LocalStorage())
        else:
            from ._reactor import ReactorWorker
            coordinator = ReactorWorker(reactor)

        team = Team(coordinator=coordinator,
                    createWorker=limitedWorkerCreator,
                    logException=err)
        return team



