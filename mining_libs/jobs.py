import binascii
import struct

import stratum.logger
log = stratum.logger.get_logger('proxy')

class JobRegistry(object):

    def __init__(self):
        self.extranonce1 = None
        self.extranonce2_size = None

        self.difficulty = 1

        self.tail_iterator = 0
        self.registered_tails = []
    
    def set_extranonce(self, extranonce1, extranonce2_size):
        self.extranonce2_size = extranonce2_size
        self.extranonce1 = extranonce1
        log.info(
            "Set extranonce: %s/%s",
            self.extranonce1,
            self.extranonce2_size)

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
