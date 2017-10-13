import hashlib
import struct

import stratum.logger
log = stratum.logger.get_logger('proxy')


def show_message(msg):
    '''Displays the message received from
    the server.'''
    log.warning("MESSAGE FROM THE SERVER OPERATOR: %s" % msg)


def format_hash(h):
    # For printing hashes to console
    return "%s" % h[:8]


def uint256_from_str(s):
    r = 0
    t = struct.unpack("<IIIIIIII", s[:32])
    for i in xrange(8):
        r += t[i] << (i * 32)
    return r


def uint256_to_str(u):
    rs = ""
    for i in xrange(8):
        rs += struct.pack("<I", u & 0xFFFFFFFF)
        u >>= 32
    return rs


def reverse_hash(h):
    return struct.pack('>IIIIIIII', *struct.unpack('>IIIIIIII', h)[::-1])[::-1]


def doublesha(b):
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()
