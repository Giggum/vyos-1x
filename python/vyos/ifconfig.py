# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import subprocess
import ipaddress
import jinja2

from vyos.validate import *
from ipaddress import IPv4Network, IPv6Address
from netifaces import ifaddresses, AF_INET, AF_INET6
from time import sleep

dhcp_cfg = """
# generated by ifconfig.py
option rfc3442-classless-static-routes code 121 = array of unsigned integer 8;
interface "{{ intf }}" {
    send host-name "{{ hostname }}";
    request subnet-mask, broadcast-address, routers, domain-name-servers, rfc3442-classless-static-routes, domain-name, interface-mtu;
}
"""

dhcpv6_cfg = """
# generated by ifconfig.py
interface "{{ intf }}" {
    request routers, domain-name-servers, domain-name;
}
"""

dhclient_base = r'/var/lib/dhcp/dhclient_'

class Interface:
    def __init__(self, ifname=None, type=None, debug=False):
        """
        Create instance of an IP interface

        Example:

        >>> from vyos.ifconfig import Interface
        >>> i = Interface('eth0')
        """

        if not ifname:
            raise Exception('interface name required')

        if not os.path.exists('/sys/class/net/{}'.format(ifname)) and not type:
            raise Exception('interface "{}" not found'.format(str(ifname)))

        # variable already referenced from _debug()
        self._debug = debug
        self._ifname = str(ifname)

        if not os.path.exists('/sys/class/net/{}'.format(ifname)):
            cmd = 'ip link add dev "{}" type "{}"'.format(ifname, type)
            self._cmd(cmd)

        # per interface DHCP config files
        self._dhcp_cfg_file = dhclient_base + self._ifname + '.conf'
        self._dhcp_pid_file = dhclient_base + self._ifname + '.pid'
        self._dhcp_lease_file = dhclient_base + self._ifname + '.leases'

        # per interface DHCPv6 config files
        self._dhcpv6_cfg_file = dhclient_base + self._ifname + '.v6conf'
        self._dhcpv6_pid_file = dhclient_base + self._ifname + '.v6pid'
        self._dhcpv6_lease_file = dhclient_base + self._ifname + '.v6leases'


    def _debug_msg(self, msg):
        if self._debug:
            print('"DEBUG/{}: {}'.format(self._ifname, msg))


    def set_debug(self, debug):
        if debug not in [True, False]:
            raise ValueError('must specify True or False for debug')
        self._debug = debug


    def remove(self):
        """
        Remove system interface

        Example:

        >>> from vyos.ifconfig import Interface
        >>> i = Interface('eth0')
        >>> i.remove()
        """

        # stop DHCP(v6) if running
        self.del_dhcp()
        self.del_dhcpv6()

        # NOTE (Improvement):
        # after interface removal no other commands should be allowed
        # to be called and instead should raise an Exception:
        cmd = 'ip link del dev "{}"'.format(self._ifname)
        self._cmd(cmd)


    def _cmd(self, command):
        self._debug_msg(command)

        process = subprocess.Popen(command,stdout=subprocess.PIPE, shell=True)
        proc_stdout = process.communicate()[0].strip()

        # add exception handling code
        pass


    @property
    def mtu(self):
        """
        Get/set interface mtu in bytes.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').mtu
        '1500'
        """

        mtu = 0
        with open('/sys/class/net/{0}/mtu'.format(self._ifname), 'r') as f:
            mtu = f.read().rstrip('\n')
        return mtu


    @mtu.setter
    def mtu(self, mtu=None):
        """
        Get/set interface mtu in bytes.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').mtu = 1400
        >>> Interface('eth0').mtu
        '1400'
        """

        if mtu < 68 or mtu > 9000:
            raise ValueError('Invalid MTU size: "{}"'.format(mru))

        with open('/sys/class/net/{0}/mtu'.format(self._ifname), 'w') as f:
            f.write(str(mtu))


    @property
    def mac(self):
        """
        Get/set interface mac address

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').mac
        '00:0c:29:11:aa:cc'
        """
        address = ''
        with open('/sys/class/net/{0}/address'.format(self._ifname), 'r') as f:
            address = f.read().rstrip('\n')
        return address


    @mac.setter
    def mac(self, mac=None):
        """
        Get/set interface mac address

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').mac = '00:90:43:fe:fe:1b'
        >>> Interface('eth0').mac
        '00:90:43:fe:fe:1b'
        """
        # a mac address consits out of 6 octets
        octets = len(mac.split(':'))
        if octets != 6:
            raise ValueError('wrong number of MAC octets: {} '.format(octets))

        # validate against the first mac address byte if it's a multicast address
        if int(mac.split(':')[0]) & 1:
            raise ValueError('{} is a multicast MAC address'.format(mac))

        # overall mac address is not allowed to be 00:00:00:00:00:00
        if sum(int(i, 16) for i in mac.split(':')) == 0:
            raise ValueError('00:00:00:00:00:00 is not a valid MAC address')

        # check for VRRP mac address
        if mac.split(':')[0] == '0' and addr.split(':')[1] == '0' and mac.split(':')[2] == '94' and mac.split(':')[3] == '0' and mac.split(':')[4] == '1':
            raise ValueError('{} is a VRRP MAC address'.format(mac))

        # Assemble command executed on system. Unfortunately there is no way
        # of altering the MAC address via sysfs
        cmd = 'ip link set dev "{}" address "{}"'.format(self._ifname, mac)
        self._cmd(cmd)


    @property
    def arp_cache_tmo(self):
        """
        Get configured ARP cache timeout value from interface. Example shows
        default value of 30 seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').arp_cache_tmo
        '30000'
        """

        alias = ''
        with open('/proc/sys/net/ipv4/neigh/{0}/base_reachable_time_ms'.format(self._ifname), 'r') as f:
            alias = f.read().rstrip('\n')
        return alias


    @arp_cache_tmo.setter
    def arp_cache_tmo(self, tmo=None):
        """
        Set ARP cache timeout value in seconds for this.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').arp_cache_tmo = '40000'
        """

        # clear interface alias
        if not tmo:
            raise ValueError('Timeout value required')

        # Kernel interface is on milli seconds
        tmo = int(tmo) * 1000
        with open('/proc/sys/net/ipv4/neigh/{0}/base_reachable_time_ms'.format(self._ifname), 'w') as f:
            f.write(str(tmo))

    @property
    def link_detect(self):
        """
        How does the kernel act when receiving packets on 'down' interfaces

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').link_detect
        '0'
        """

        alias = ''
        with open('/proc/sys/net/ipv4/conf/{0}/link_filter'.format(self._ifname), 'r') as f:
            alias = f.read().rstrip('\n')
        return alias


    @link_detect.setter
    def link_detect(self, link_filter=None):
        """
        Konfigure kernel response in packets received on interfaces that are 'down'

        0 - Allow packets to be received for the address on this interface
            even if interface is disabled or no carrier.

        1 - Ignore packets received if interface associated with the incoming
            address is down.

        2 - Ignore packets received if interface associated with the incoming
            address is down or has no carrier.

        Default value is 0. Note that some distributions enable it in startup
        scripts.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').link_detect = '1'
        """

        # clear interface alias
        if not link_filter:
            raise ValueError()

        if link_filter >= 0 and link_filter <= 2:
            with open('/proc/sys/net/ipv4/conf/{0}/link_filter'.format(self._ifname), 'w') as f:
                f.write(str(link_filter))
        else:
            raise ValueError()


    @property
    def ifalias(self):
        """
        Get/set interface alias name

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').ifalias
        ''
        """

        alias = ''
        with open('/sys/class/net/{0}/ifalias'.format(self._ifname), 'r') as f:
            alias = f.read().rstrip('\n')
        return alias


    @ifalias.setter
    def ifalias(self, ifalias=None):
        """
        Get/set interface alias name

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').ifalias = 'VyOS upstream interface'
        >>> Interface('eth0').ifalias
        'VyOS upstream interface'

        to clear interface alias e.g. delete it use:

        >>> Interface('eth0').ifalias = ''
        >>> Interface('eth0').ifalias
        ''
        """

        # clear interface alias
        if not ifalias:
            ifalias = '\0'

        with open('/sys/class/net/{0}/ifalias'.format(self._ifname), 'w') as f:
            f.write(str(ifalias))


    @property
    def state(self):
        """
        Enable (up) / Disable (down) an interface

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').state
        'up'
        """

        state = ''
        with open('/sys/class/net/{0}/operstate'.format(self._ifname), 'r') as f:
            state = f.read().rstrip('\n')
        return state


    @state.setter
    def state(self, state=None):
        """
        Enable (up) / Disable (down) an interface

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').state = 'down'
        >>> Interface('eth0').state
        'down'
        """

        if state not in ['up', 'down']:
            raise ValueError('state must be "up" or "down"')

        # Assemble command executed on system. Unfortunately there is no way
        # to up/down an interface via sysfs
        cmd = 'ip link set dev "{}" "{}"'.format(self._ifname, state)
        self._cmd(cmd)


    def get_addr(self):
        """
        Retrieve assigned IPv4 and IPv6 addresses from given interface.
        This is done using the netifaces and ipaddress python modules.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_addrs()
        ['172.16.33.30/24', 'fe80::20c:29ff:fe11:a174/64']
        """

        ipv4 = []
        ipv6 = []

        if AF_INET in ifaddresses(self._ifname).keys():
            for v4_addr in ifaddresses(self._ifname)[AF_INET]:
                # we need to manually assemble a list of IPv4 address/prefix
                prefix = '/' + str(IPv4Network('0.0.0.0/' + v4_addr['netmask']).prefixlen)
                ipv4.append( v4_addr['addr'] + prefix )

        if AF_INET6 in ifaddresses(self._ifname).keys():
            for v6_addr in ifaddresses(self._ifname)[AF_INET6]:
                # Note that currently expanded netmasks are not supported. That means
                # 2001:db00::0/24 is a valid argument while 2001:db00::0/ffff:ff00:: not.
                # see https://docs.python.org/3/library/ipaddress.html
                bits =  bin( int(v6_addr['netmask'].replace(':',''), 16) ).count('1')
                prefix = '/' + str(bits)

                # we alsoneed to remove the interface suffix on link local addresses
                v6_addr['addr'] = v6_addr['addr'].split('%')[0]
                ipv6.append( v6_addr['addr'] + prefix )

        return ipv4 + ipv6


    def add_addr(self, addr=None):
        """
        Add IP address to interface. Address is only added if it yet not added
        to that interface.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.add_addr('192.0.2.1/24')
        >>> j.add_addr('2001:db8::ffff/64')
        >>> j.get_addr()
        ['192.0.2.1/24', '2001:db8::ffff/64']
        """

        if not addr:
            raise ValueError('No IP address specified')

        if not is_intf_addr_assigned(self._ifname, addr):
            cmd = 'sudo ip addr add "{}" dev "{}"'.format(addr, self._ifname)
            self._cmd(cmd)


    def del_addr(self, addr=None):
        """
        Remove IP address from interface.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.add_addr('2001:db8::ffff/64')
        >>> j.add_addr('192.0.2.1/24')
        >>> j.get_addr()
        ['192.0.2.1/24', '2001:db8::ffff/64']
        >>> j.del_addr('192.0.2.1/24')
        >>> j.get_addr()
        ['2001:db8::ffff/64']
        """

        if not addr:
            raise ValueError('No IP address specified')

        if is_intf_addr_assigned(self._ifname, addr):
            cmd = 'ip addr del "{}" dev "{}"'.format(addr, self._ifname)
            self._cmd(cmd)


    # replace dhcpv4/v6 with systemd.networkd?
    def set_dhcp(self):
        """
        Configure interface as DHCP client. The dhclient binary is automatically
        started in background!

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.set_dhcp()
        """

        dhcp = {
            'hostname': 'vyos',
            'intf': self._ifname
        }

        # read configured system hostname.
        # maybe change to vyos hostd client ???
        with open('/etc/hostname', 'r') as f:
            dhcp['hostname'] = f.read().rstrip('\n')

        # render DHCP configuration
        tmpl = jinja2.Template(dhcp_cfg)
        dhcp_text = tmpl.render(dhcp)
        with open(self._dhcp_cfg_file, 'w') as f:
            f.write(dhcp_text)

        cmd  = 'start-stop-daemon --start --quiet --pidfile ' + self._dhcp_pid_file
        cmd += ' --exec /sbin/dhclient --'
        # now pass arguments to dhclient binary
        cmd += ' -4 -nw -cf {} -pf {} -lf {} {}'.format(self._dhcp_cfg_file, self._dhcp_pid_file, self._dhcp_lease_file, self._ifname)
        self._cmd(cmd)


    def del_dhcp(self):
        """
        De-configure interface as DHCP clinet. All auto generated files like
        pid, config and lease will be removed.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.del_dhcp()
        """

        pid = 0
        if os.path.isfile(self._dhcp_pid_file):
            with open(self._dhcp_pid_file, 'r') as f:
                pid = int(f.read())
        else:
            self._debug_msg('No DHCP client PID found')
            return None

        # stop dhclient
        cmd = 'start-stop-daemon --stop --quiet --pidfile {}'.format(self._dhcp_pid_file)
        self._cmd(cmd)

        # cleanup old config file
        if os.path.isfile(self._dhcp_cfg_file):
            os.remove(self._dhcp_cfg_file)

        # cleanup old pid file
        if os.path.isfile(self._dhcp_pid_file):
            os.remove(self._dhcp_pid_file)

        # cleanup old lease file
        if os.path.isfile(self._dhcp_lease_file):
            os.remove(self._dhcp_lease_file)


    def set_dhcpv6(self):
        """
        Configure interface as DHCPv6 client. The dhclient binary is automatically
        started in background!

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.set_dhcpv6()
        """

        dhcpv6 = {
            'intf': self._ifname
        }

        # render DHCP configuration
        tmpl = jinja2.Template(dhcpv6_cfg)
        dhcpv6_text = tmpl.render(dhcpv6)
        with open(self._dhcpv6_cfg_file, 'w') as f:
            f.write(dhcpv6_text)

        # https://bugs.launchpad.net/ubuntu/+source/ifupdown/+bug/1447715
        #
        # wee need to wait for IPv6 DAD to finish once and interface is added
        # this suxx :-(
        sleep(5)

        # no longer accept router announcements on this interface
        cmd = 'sysctl -q -w net.ipv6.conf.{}.accept_ra=0'.format(self._ifname)
        self._cmd(cmd)

        cmd  = 'start-stop-daemon --start --quiet --pidfile ' + self._dhcpv6_pid_file
        cmd += ' --exec /sbin/dhclient --'
        # now pass arguments to dhclient binary
        cmd += ' -6 -nw -cf {} -pf {} -lf {} {}'.format(self._dhcpv6_cfg_file, self._dhcpv6_pid_file, self._dhcpv6_lease_file, self._ifname)
        self._cmd(cmd)


    def del_dhcpv6(self):
        """
        De-configure interface as DHCPv6 clinet. All auto generated files like
        pid, config and lease will be removed.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.del_dhcpv6()
        """

        pid = 0
        if os.path.isfile(self._dhcpv6_pid_file):
            with open(self._dhcpv6_pid_file, 'r') as f:
                pid = int(f.read())
        else:
            self._debug_msg('No DHCPv6 client PID found')
            return None

        # stop dhclient
        cmd = 'start-stop-daemon --stop --quiet --pidfile {}'.format(self._dhcpv6_pid_file)
        self._cmd(cmd)

        # accept router announcements on this interface
        cmd = 'sysctl -q -w net.ipv6.conf.{}.accept_ra=1'.format(self._ifname)
        self._cmd(cmd)

        # cleanup old config file
        if os.path.isfile(self._dhcpv6_cfg_file):
            os.remove(self._dhcpv6_cfg_file)

        # cleanup old pid file
        if os.path.isfile(self._dhcpv6_pid_file):
            os.remove(self._dhcpv6_pid_file)

        # cleanup old lease file
        if os.path.isfile(self._dhcpv6_lease_file):
            os.remove(self._dhcpv6_lease_file)


class LoopbackIf(Interface):
    def __init__(self, ifname=None):
        super().__init__(ifname, type='loopback')


class DummyIf(Interface):
    def __init__(self, ifname=None):
        super().__init__(ifname, type='dummy')


class BridgeIf(Interface):
    def __init__(self, ifname=None):
        super().__init__(ifname, type='bridge')

    @property
    def ageing_time(self):
        """
        Get bridge aging time in seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').aging_time
        '3'
        """

        time = 0
        with open('/sys/class/net/{0}/bridge/ageing_time'.format(self._ifname), 'r') as f:
            time = int(f.read().rstrip('\n'))

        # kernel representation is in centiseconds - convert to seconds
        return time/100


    @ageing_time.setter
    def ageing_time(self, time=None):
        """
        Set bridge aging time in seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').ageing_time = 2
        """

        if not time:
            raise ValueError()

        # kernel representation is in centiseconds - convert from seconds to centiseconds
        time = int(time) * 100

        with open('/sys/class/net/{0}/bridge/ageing_time'.format(self._ifname), 'w') as f:
            f.write(str(time))

    @property
    def forward_delay(self):
        """
        Get bridge forwarding delay in seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').ageing_time
        '3"""

        time = 0
        with open('/sys/class/net/{0}/bridge/forward_delay'.format(self._ifname), 'r') as f:
            time = int(f.read().rstrip('\n'))

        # kernel representation is in centiseconds - convert to seconds
        return time/100


    @forward_delay.setter
    def forward_delay(self, time=None):
        """
        Set bridge forwarding delay in seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').forward_delay = 15
        """

        if not time:
            raise ValueError()

        # kernel representation is in centiseconds - convert from seconds to centiseconds
        time = int(time) * 100

        with open('/sys/class/net/{0}/bridge/forward_delay'.format(self._ifname), 'w') as f:
            f.write(str(time))

    @property
    def hello_time(self):
        """
        Get bridge hello time in seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').hello_time
        '2'
        """

        time = 0
        with open('/sys/class/net/{0}/bridge/hello_time'.format(self._ifname), 'r') as f:
            time = int(f.read().rstrip('\n'))

        # kernel representation is in centiseconds - convert to seconds
        return time/100


    @hello_time.setter
    def hello_time(self, time=None):
        """
        Set bridge hello time in seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').hello_time = 2
        """

        if not time:
            raise ValueError()

        # kernel representation is in centiseconds - convert from seconds to centiseconds
        time = int(time) * 100

        with open('/sys/class/net/{0}/bridge/hello_time'.format(self._ifname), 'w') as f:
            f.write(str(time))

    @property
    def max_age(self):
        """
        Get bridge max max message age in seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').max_age
        '20'
        """

        time = 0
        with open('/sys/class/net/{0}/bridge/max_age'.format(self._ifname), 'r') as f:
            time = int(f.read().rstrip('\n'))

        # kernel representation is in centiseconds - convert to seconds
        return time/100


    @max_age.setter
    def max_age(self, time=None):
        """
        Set bridge max message age in seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').max_age = 30
        """

        if not time:
            raise ValueError()

        # kernel representation is in centiseconds - convert from seconds to centiseconds
        time = int(time) * 100

        with open('/sys/class/net/{0}/bridge/max_age'.format(self._ifname), 'w') as f:
            f.write(str(time))

    @property
    def priority(self):
        """
        Get bridge max aging time in seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').priority
        '32768'
        """

        priority = 0
        with open('/sys/class/net/{0}/bridge/priority'.format(self._ifname), 'r') as f:
            priority = int(f.read().rstrip('\n'))

        # kernel representation is in centiseconds - convert to seconds
        return priority


    @priority.setter
    def priority(self, priority=None):
        """
        Set bridge max aging time in seconds.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').priority = 8192
        """

        if not priority:
            raise ValueError()

        with open('/sys/class/net/{0}/bridge/priority'.format(self._ifname), 'w') as f:
            f.write(str(priority))


    @property
    def stp_state(self):
        """
        Get bridge STP state

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').stp_state
        '0'
        """

        state = 0
        with open('/sys/class/net/{0}/bridge/stp_state'.format(self._ifname), 'r') as f:
            state = int(f.read().rstrip('\n'))

        return state


    @stp_state.setter
    def stp_state(self, state=None):
        """
        Set bridge STP state.
        0 -> STP disabled, 1 -> STP enabled

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').stp_state = 1
        """

        if int(state) >= 0 and int(state) <= 1:
            with open('/sys/class/net/{0}/bridge/stp_state'.format(self._ifname), 'w') as f:
                f.write(str(state))
        else:
            raise ValueError()


    @property
    def multicast_querier(self):
        """
        Get bridge multicast querier membership state.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').multicast_querier
        '0'
        """

        enable = 0
        with open('/sys/class/net/{0}/bridge/multicast_querier'.format(self._ifname), 'r') as f:
            enable = int(f.read().rstrip('\n'))

        return enable


    @multicast_querier.setter
    def multicast_querier(self, enable=None):
        """
        Sets whether the bridge actively runs a multicast querier or not. When a
        bridge receives a 'multicast host membership' query from another network
        host, that host is tracked based on the time that the query was received
        plus the multicast query interval time.

        Use enable=1 to enable or enable=0 to disable

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').multicast_querier = 1
        """

        if int(enable) >= 0 and int(enable) <= 1:
            with open('/sys/class/net/{0}/bridge/multicast_querier'.format(self._ifname), 'w') as f:
                f.write(str(enable))
        else:
            raise ValueError()


    def add_port(self, interface=None):
        """
        Add bridge member port

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').add_port('eth0')
        >>> BridgeIf('br0').add_port('eth1')
        """

        if not interface:
            raise ValueError('No interface address specified')

        cmd = 'ip link set dev "{}" master "{}"'.format(interface, self._ifname)
        self._cmd(cmd)


    def del_port(self, interface=None):
        """
        Add bridge member port

        Example:

        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').del_port('eth1')
        """

        if not interface:
            raise ValueError('No interface address specified')

        cmd = 'ip link set dev "{}" nomaster'.format(interface)
        self._cmd(cmd)


    def set_cost(self, interface=None, cost=None):
        """
        Set interface path cost, only relevant for STP enabled interfaces

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').path_cost(4)
        """

        if not interface:
            raise ValueError('interface not specified')

        if not cost:
            raise ValueError('cost not specified')

        with open('/sys/class/net/{}/brif/{}/path_cost'.format(self._ifname, interface), 'w') as f:
            f.write(str(cost))


    def set_priority(self, interface=None, priority=None):
        """
        Set interface path priority, only relevant for STP enabled interfaces

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').priority(4)
        """

        if not interface:
            raise ValueError('interface not specified')

        if not priority:
            raise ValueError('priority not specified')

        with open('/sys/class/net/{}/brif/{}/priority'.format(self._ifname, interface), 'w') as f:
            f.write(str(priority))
