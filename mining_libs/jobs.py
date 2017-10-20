import binascii
import time
import struct

import utils

import stratum.logger
log = stratum.logger.get_logger('proxy')


class Job(object):

    def __init__(self):
        self.job_id = None
        self.prevhash = ''
        self.coinb1_bin = ''
        self.coinb2_bin = ''
        self.merkle_branch = []
        self.version = 1
        self.nbits = 0
        self.ntime_delta = 0
        self.diff = 1
        self.extranonce2 = 0

    @classmethod
    def build_from_broadcast(
            cls,
            job_id,
            prevhash,
            coinb1,
            coinb2,
            merkle_branch,
            version,
            nbits,
            ntime,
            diff):
        '''Build job object from Stratum server broadcast'''
        job = Job()
        job.job_id = job_id
        job.prevhash = prevhash
        job.coinb1_bin = binascii.unhexlify(coinb1)
        job.coinb2_bin = binascii.unhexlify(coinb2)
        job.merkle_branch = [binascii.unhexlify(tx) for tx in merkle_branch]
        job.version = version
        job.nbits = nbits
        job.ntime_delta = int(ntime, 16) - int(time.time())
        job.diff = diff
        return job

class JobRegistry(object):

    def __init__(self, scrypt_target=False):
        # calculate target for scrypt algorithm instead of sha256
        self.scrypt_target = scrypt_target
        self.jobs = []
        self.last_job = None
        self.extranonce1 = None
        self.extranonce1_bin = None
        self.extranonce2_size = None

        self.target = 0
        self.target_hex = ''
        self.difficulty = 1
        self.set_difficulty(1)
        self.target1_hex = self.target_hex

        self.tail_iterator = 0
        self.registered_tails = []
    
    def set_extranonce(self, extranonce1, extranonce2_size):
        self.extranonce2_size = extranonce2_size
        self.extranonce1_bin = binascii.unhexlify(extranonce1)
        self.extranonce1 = extranonce1
        log.info(
            "Set extranonce: %s/%s",
            self.extranonce1,
            self.extranonce2_size)

    def set_difficulty(self, new_difficulty):
        if self.scrypt_target:
            dif1 = 0x0000ffff00000000000000000000000000000000000000000000000000000000
        else:
            dif1 = 0x00000000ffff0000000000000000000000000000000000000000000000000000
        self.target = int(dif1 / new_difficulty)
        self.target_hex = binascii.hexlify(utils.uint256_to_str(self.target))
        self.difficulty = new_difficulty

    def build_full_extranonce(self, extranonce2):
        '''Join extranonce1 and extranonce2 together while padding
        extranonce2 length to extranonce2_size (provided by server).'''
        return self.extranonce1_bin + self.extranonce2_padding(extranonce2)

    def extranonce2_padding(self, extranonce2):
        '''Return extranonce2 with padding bytes'''

        if not self.extranonce2_size:
            raise Exception("Extranonce2_size isn't set yet")

        extranonce2_bin = struct.pack('>I', extranonce2)
        missing_len = self.extranonce2_size - len(extranonce2_bin)

        if missing_len < 0:
            # extranonce2 is too long, we should print warning on console,
            # but try to shorten extranonce2
            log.info(
                "Extranonce size mismatch. Please report this error to pool operator!")
            return extranonce2_bin[abs(missing_len):]

        # This is probably more common situation, but it is perfectly
        # safe to add whitespaces
        return '\x00' * missing_len + extranonce2_bin

    def add_template(self, template, clean_jobs):
        if clean_jobs:
            # Pool asked us to stop submitting shares from previous jobs
            self.jobs = []

        self.jobs.append(template)
        self.last_job = template

    def get_job_from_id(self, job_id):
        job = None
        for j in self.jobs:
            if j.job_id == job_id:
                job = j
                break
        return job

    def _var_int(self, i):
        if i <= 0xff:
            return struct.pack('>B', i)
        elif i <= 0xffff:
            return struct.pack('>H', i)
        raise Exception("number is too big")

    def _get_unused_tail(self):
        '''Currently adds up to two bytes to extranonce1,
        limiting proxy for up to 65535 connected clients.'''

        for _ in range(0, 0xffff):  # 0-65535
            self.tail_iterator += 1
            self.tail_iterator %= 0xffff

            # Zero extranonce is reserved for getwork connections
            if self.tail_iterator == 0:
                self.tail_iterator += 1

            # var_int throws an exception when input is >= 0xffff
            tail = self._var_int(self.tail_iterator)
            tail_len = len(tail)

            if tail not in self.registered_tails:
                self.registered_tails.append(tail)
                return (
                    binascii.hexlify(tail),
                    self.extranonce2_size -
                    tail_len)

        raise Exception(
            "Extranonce slots are full, please disconnect some miners!")

    def _drop_tail(self, result, tail):
        tail = binascii.unhexlify(tail)
        if tail in self.registered_tails:
            self.registered_tails.remove(tail)
        else:
            log.error("Given extranonce is not registered1")
        return result
