from stratum.event_handler import GenericEventHandler
from jobs import Job
import version as _version
import stratum_listener

import stratum.logger
log = stratum.logger.get_logger('proxy')

import stproxy_ng

class ClientMiningService(GenericEventHandler):

    def handle_event(self, method, params, connection_ref):
        '''Handle RPC calls and notifications from the pool'''

        stp = stproxy_ng.StratumServer.pool2proxy[id(connection_ref.factory)]

        if method == 'mining.notify':
            '''Proxy just received information about new mining job'''

            (job_id,
             prevhash,
             coinb1,
             coinb2,
             merkle_branch,
             version,
             nbits,
             ntime,
             clean_jobs) = params[:9]

            diff = stp.difficulty

            # print len(str(params)), len(merkle_branch)
            '''
            log.debug("Received new job #%s" % job_id)
            log.debug("prevhash = %s" % prevhash)
            log.debug("version = %s" % version)
            log.debug("nbits = %s" % nbits)
            log.debug("ntime = %s" % ntime)
            log.debug("clean_jobs = %s" % clean_jobs)
            log.debug("coinb1 = %s" % coinb1)
            log.debug("coinb2 = %s" % coinb2)
            log.debug("merkle_branch = %s" % merkle_branch)
            log.debug("difficulty = %s" % diff)
            '''

            # Broadcast to Stratum clients
            stratum_listener.MiningSubscription.on_template(
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

            # Broadcast to getwork clients
            job = Job.build_from_broadcast(
                job_id,
                prevhash,
                coinb1,
                coinb2,
                merkle_branch,
                version,
                nbits,
                ntime,
                diff)
            log.info("New job %s for prevhash %s, clean_jobs=%s" %
                     (job.job_id, job.prevhash[:8], clean_jobs))

            stp.job_registry.add_template(job, clean_jobs)

        elif method == 'mining.set_difficulty':
            difficulty = params[0]
            log.info("Setting new difficulty: %s" % difficulty)
            stratum_listener.DifficultySubscription.on_new_difficulty(
                stp,
                difficulty)

        elif method == 'client.reconnect':
            try:
                (hostname, port, wait) = params[:3]
            except:
                log.error("Pool sent client.reconnect")
                hostname = False
                port = False
                wait = False
            new = list(stp.f.main_host[::])
            if hostname and len(hostname) > 6:
                new[0] = hostname
            if port and port > 2:
                new[1] = port
            log.info("Reconnecting to %s:%d" % tuple(new))
            stp.f.reconnect(new[0], new[1], wait)

        elif method == 'mining.set_extranonce':
            '''Method to set new extranonce'''
            try:
                extranonce1 = params[0]
                extranonce2_size = params[1]
                log.info(
                    "Setting new extranonce: %s/%s" %
                    (extranonce1, extranonce2_size))
            except:
                log.error(
                    "Wrong extranonce information got from pool, ignoring")
                return False
            stp.job_registry.set_extranonce(
                extranonce1,
                int(extranonce2_size))
            log.info('Sending reconnect order to workers')
            stratum_listener.MiningSubscription.reconnect_all()
            return True

        elif method == 'client.add_peers':
            '''New peers which can be used on connection failure'''
            return False
            '''
            peerlist = params[0] # TODO
            for peer in peerlist:
                stp.f.add_peer(peer)
            return True
            '''
        elif method == 'client.get_version':
            return "stratum-proxy/%s" % _version.VERSION

        elif method == 'client.show_message':

            # Displays message from the server to the terminal
            log.warning("MESSAGE FROM THE SERVER OPERATOR: %s" % params[0])
            return True

        elif method == 'mining.get_hashrate':
            return {}  # TODO

        elif method == 'mining.get_temperature':
            return {}  # TODO

        else:
            '''Pool just asked us for something which we don't support...'''
            log.error("Unhandled method %s with params %s" % (method, params))
