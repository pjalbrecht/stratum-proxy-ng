import time
from twisted.internet import defer
from stratum.services import GenericService
from stratum.pubsub import Pubsub, Subscription
from stratum.custom_exceptions import ServiceException, RemoteServiceException

import stratum.logger
log = stratum.logger.get_logger('proxy')

import stproxy_ng

from control import ShareSubscription, MinerConnectSubscription

class SubscribeException(ServiceException):
    code = -2

class SubmitException(ServiceException):
    code = -2

class BlacklistException(ServiceException):
    code = -2

class DifficultySubscription(Subscription):

    @classmethod
    def on_new_difficulty(cls, stp, new_difficulty):
        stp.job_registry.difficulty = new_difficulty
        DifficultySubscription.publish_all(stp, new_difficulty)

    def __init__(self, stp):
        Subscription.__init__(self, 'mining.set_difficulty' + str(id(stp)))
        self.stp = stp

    def after_subscribe(self, result):
        self.publish_one(self.stp.job_registry.difficulty)
        return result

    @classmethod
    def publish_all(cls, stp, *args):
        for subs in Pubsub.iterate_subscribers('mining.set_difficulty' + str(id(stp))):
            conn = subs.connection_ref()

            if conn is None or conn.transport is None:
                continue

            conn.writeJsonRequest('mining.set_difficulty', args, is_notification=True)

    def publish_one(self, *args):
        conn = self.connection_ref()

        if conn is None or conn.transport is None:
           return

        conn.writeJsonRequest('mining.set_difficulty', args, is_notification=True)

class MiningSubscription(Subscription):

    @classmethod
    def reconnect_all(cls, stp):
        for subs in Pubsub.iterate_subscribers('mining.notify' + str(id(stp))):
            conn = subs.connection_ref()

            if conn is None or conn.transport is None:
                continue

            conn.transport.loseConnection()

    @classmethod
    def publish_all(cls, stp, *args):
        for subs in Pubsub.iterate_subscribers('mining.notify' + str(id(stp))):
            conn = subs.connection_ref()

            if conn is None or conn.transport is None:
                continue

            conn.writeJsonRequest('mining.notify', args, is_notification=True)

    def publish_one(self, *args):
        conn = self.connection_ref()

        if conn is None or conn.transport is None:
           return

        conn.writeJsonRequest('mining.notify', args, is_notification=True)

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
        MiningSubscription.publish_all(
            stp,
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
        Subscription.__init__(self, 'mining.notify' + str(id(stp)))
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

        self.publish_one(
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

    def authorize(self, worker_name, worker_password, *args):
        return True

    @defer.inlineCallbacks
    def subscribe(self, *args):
        conn = self.connection_ref()

        if conn is None or not conn.transport:
            log.info('subscribe miner connection lost.............................%s', conn)
            raise SubscribeException("Miner connection lost")

        stp = stproxy_ng.StratumServer.miner2proxy.setdefault(conn._get_ip(), stproxy_ng.StratumServer.stp)

        if stp is None:
            log.info('subscribe miner blacklisted.................................%s', conn)
            raise BlacklistException('Miner blacklisted')

        try:
            yield stp.connected
            log.info('subscribe yield proxy connected result......................%s %s', conn, stp)
        except Exception as e:
            log.info('subscribe yield proxy connected exception.................. %s %s %s', conn, stp, e)

        if not conn.transport:
            log.info('subscribe miner connection lost.............................%s %s', conn, stp)
            raise SubscribeException("Miner connection lost")

        conn.on_disconnect.addCallback(stp.miner_disconnect, conn._get_ip())
        MinerConnectSubscription.emit(conn._get_ip(), id(stp.f))

        session = conn.get_session()
        session['proxy'] = stp

        session['subscribed'] = int(round(time.time()))

        session['shares_sent'] = 0

        (tail, extranonce2_size) = stp.job_registry._get_unused_tail()
        # Remove extranonce from registry when client disconnect
        conn.on_disconnect.addCallback(stp.job_registry._drop_tail, tail)
        session['tail'] = tail

        subs1 = Pubsub.subscribe(conn, DifficultySubscription(stp))[0][1]
        subs2 = Pubsub.subscribe(conn, MiningSubscription(stp))[0][1]

        log.info(
            "Sending subscription to worker: %s/%s connection: %s proxy: %s",
            stp.job_registry.extranonce1 + tail, extranonce2_size, conn, stp)

        defer.returnValue( ((('mining.set_difficulty',subs1), ('mining.notify', subs2)),) + (stp.job_registry.extranonce1 + tail, extranonce2_size) )

    @defer.inlineCallbacks
    def submit(
            self,
            origin_worker_name,
            job_id,
            extranonce2,
            ntime,
            nonce,
            *args):
        conn = self.connection_ref()

        if conn is None or not conn.transport:
            log.info('submit miner connection lost................................%s', conn)
            raise SubmitException("Miner connection lost")

        session = conn.get_session()

        try:
            stp = session['proxy']
        except KeyError:
            log.info('submit miner is not connected to proxy......................%s', conn)
            raise SubmitException("Connection is not connected to proxy")

        try:
            tail = session['tail']
        except KeyError:
            log.info('submit miner is not subscribed..............................%s %s', conn, stp)
            raise SubmitException("Connection is not subscribed")

        worker_name = stp.auth[0]

        difficulty = stp.job_registry.difficulty

        start = time.time()

        session['last_share'] = int(round(start))

        session['shares_sent'] += 1

        try:
            result = (yield stp.f.rpc('mining.submit', [worker_name, job_id, tail + extranonce2, ntime, nonce]))
        except RemoteServiceException as exc:
            response_time = (time.time() - start) * 1000
            log.info(
                "[%dms] Share from %s (%s) REJECTED, diff %d: %s",
                response_time,
                 origin_worker_name,
                 worker_name,
                 difficulty,
                 str(exc))
            ShareSubscription.emit(start, id(stp.f), job_id, stp.f.client._get_ip(), origin_worker_name, worker_name, difficulty, False)
            raise SubmitException(*exc.args)

        response_time = (time.time() - start) * 1000

        log.info(
            "[%dms] Share from %s (%s) ACCEPTED, diff %d",
            response_time,
             origin_worker_name,
             worker_name,
             difficulty)

        ShareSubscription.emit(start, id(stp.f), job_id, stp.f.client._get_ip(), origin_worker_name, worker_name, difficulty, True)

        defer.returnValue(result)

    def get_transactions(self, *args):
        log.warn("mining.get_transactions is not supported")
        return []
