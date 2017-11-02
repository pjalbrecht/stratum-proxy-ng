import time
from twisted.internet import defer
from stratum.services import GenericService
from stratum.pubsub import Pubsub, Subscription
from stratum.custom_exceptions import ServiceException, RemoteServiceException

import stratum.logger
log = stratum.logger.get_logger('proxy')

from control import ShareSubscription

class SubmitException(ServiceException):
    code = -2

class DifficultySubscription(Subscription):
    event = 'mining.set_difficulty'

    @classmethod
    def on_new_difficulty(cls, stp, new_difficulty):
        stp.difficulty = new_difficulty
        cls.emit(new_difficulty)

    def __init__(self, stp):
        Subscription.__init__(self)
        self.stp = stp

    def after_subscribe(self, result):
        self.emit_single(self.stp.difficulty)
        return result


class MiningSubscription(Subscription):
    event = 'mining.notify'

    @classmethod
    def reconnect_all(cls):
        for subs in Pubsub.iterate_subscribers(cls.event):
            if subs.connection_ref().transport is not None:
                subs.connection_ref().transport.loseConnection()

    @classmethod
    def on_template(
            cls,
            stp,
            job_id,
            prevhash,
            coinb1,
            coinb2,
            merkle_branch,
            version,
            nbits,
            ntime,
            clean_jobs):
        '''Push new job to subscribed clients'''
        stp.last_broadcast = (
            job_id,
            prevhash,
            coinb1,
            coinb2,
            merkle_branch,
            version,
            nbits,
            ntime,
            clean_jobs)
        cls.emit(
            job_id,
            prevhash,
            coinb1,
            coinb2,
            merkle_branch,
            version,
            nbits,
            ntime,
            clean_jobs)

    def __init__(self, stp):
        Subscription.__init__(self)
        self.stp = stp

    def after_subscribe(self, result):
        '''Send new job to newly subscribed client'''
        try:
            (job_id,
             prevhash,
             coinb1,
             coinb2,
             merkle_branch,
             version,
             nbits,
             ntime,
             _) = self.stp.last_broadcast
        except Exception:
            log.error("Template not ready yet")
            return result

        self.emit_single(
            job_id,
            prevhash,
            coinb1,
            coinb2,
            merkle_branch,
            version,
            nbits,
            ntime,
            True)
        return result

class StratumProxyService(GenericService):
    service_type = 'mining'
    service_vendor = 'mining_proxy'
    is_default = True
    stp = None  # Reference to StratumProxy instance

    @classmethod
    def _set_stratum_proxy(cls, stp):
        cls.stp = stp

    @classmethod
    def _get_stratum_proxy(cls):
        return cls.stp

    def authorize(self, worker_name, worker_password, *args):
        return True

    def subscribe(self, *args):
        stp = self._get_stratum_proxy()
        job_registry = self._get_stratum_proxy().job_registry

        conn = self.connection_ref()

        (tail, extranonce2_size) = job_registry._get_unused_tail()
        session = self.connection_ref().get_session()
        session['tail'] = tail
        # Remove extranonce from registry when client disconnect
        conn.on_disconnect.addCallback(job_registry._drop_tail, tail)
        subs1 = Pubsub.subscribe(conn, DifficultySubscription(stp))[0]
        subs2 = Pubsub.subscribe(conn, MiningSubscription(stp))[0]
        log.info(
            "Sending subscription to worker: %s/%s" %
            (job_registry.extranonce1 + tail, extranonce2_size))
        return ((subs1, subs2),) + (job_registry.extranonce1 + tail, extranonce2_size)

    @defer.inlineCallbacks
    def submit(
            self,
            origin_worker_name,
            job_id,
            extranonce2,
            ntime,
            nonce,
            *args):
        stp = self._get_stratum_proxy()
        f = self._get_stratum_proxy().f
        job_registry = self._get_stratum_proxy().job_registry

        session = self.connection_ref().get_session()
        tail = session.get('tail')
        if tail is None:
            raise SubmitException("Connection is not subscribed")

        worker_name = stp.auth[0]

        start = time.time()
        # We got something from pool, reseting client_service timeout

        try:
            job = job_registry.get_job_from_id(job_id)
            difficulty = job.diff if job is not None else stp.difficulty
            result = (yield f.rpc('mining.submit', [worker_name, job_id, tail + extranonce2, ntime, nonce]))
        except RemoteServiceException as exc:
            response_time = (time.time() - start) * 1000
            log.info(
                "[%dms] Share from %s (%s) REJECTED, diff %d: %s" %
                (response_time,
                 origin_worker_name,
                 worker_name,
                 difficulty,
                 str(exc)))
            ShareSubscription.emit(job_id, worker_name, difficulty, False)
            raise SubmitException(*exc.args)

        response_time = (time.time() - start) * 1000
        log.info(
            "[%dms] Share from %s (%s) ACCEPTED, diff %d" %
            (response_time,
             origin_worker_name,
             worker_name,
             difficulty))
        ShareSubscription.emit(job_id, worker_name, difficulty, True)
        defer.returnValue(result)

    def get_transactions(self, *args):
        log.warn("mining.get_transactions is not supported")
        return []
