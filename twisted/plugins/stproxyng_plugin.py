from zope.interface import implements

from twisted.application.service import IServiceMaker
from twisted.application import internet
from twisted.plugin import IPlugin

import sys

class Options:
     def parseOptions(self, commandline):
          self.args = parse_args(commandline)

from stratum import settings
from stproxy_ng import parse_args
from stproxy_ng import StratumServer
from mining_libs import stratum_listener
from mining_libs import stratum_control

class StratumServiceMaker(object):
     implements(IServiceMaker, IPlugin)
     tapname = "stratum-proxy"
     description = "A stratum proxy."
     options = Options

     def makeService(self, options):
          ss = StratumServer(options.args, stratum_listener, stratum_control)
          return internet.TCPServer(options.args.stratum_port, ss.stf)

serviceMaker = StratumServiceMaker()
