stratum-proxy-ng
====================

Reworking of next gen stratum proxy.

New features
====================

1. Structured as twistd application.
2. Support for multiple pools.
3. Configuration via file.
4. Control via rpc messages.
5. Share notifications via rpc.

Installation on Linux using Git
-------------------------------

1. git clone git://github.com/pjalbrecht/stratum-proxy-ng.git
2. cd stratum-mining-proxy
3. edit config.py
4. twistd -y stproxy_ng.tac
