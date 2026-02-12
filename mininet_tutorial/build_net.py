#!/usr/bin/python
 
 
from mininet.net import Mininet
from mininet.node import Controller, OVSController, RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.topo import Topo
import os
import os.path

def main():
    setLogLevel('info')

    ### DON't CHANGE as we use default SDN controller
    net = Mininet(controller=Controller, switch=OVSSwitch )
    c1 = net.addController( 'c1', controller=Controller)

    # build a network of dumbbel topology
    #   h1---s1          s5---h2    
    #          \        /
    #           s3 --- s4 
    #          /        \       
    #        s2          s6---h3

    ## added nodes: switches and hosts
    s1 = net.addSwitch("s1", mac = 11)
    s2 = net.addSwitch("s2", mac = 12)
    s3 = net.addSwitch("s3", mac = 13)
    s4 = net.addSwitch("s4", mac = 14)
    s5 = net.addSwitch("s5", mac = 15)
    s6 = net.addSwitch("s6", mac = 16)
    h1 = net.addHost('h1', ip='10.0.0.1')
    h2 = net.addHost('h2', ip='10.0.0.2')
    h3 = net.addHost('h3', ip='10.0.0.3')

    ## added links connecting nodes
    net.addLink('s1', 's3')
    net.addLink('s2', 's3')
    net.addLink('s3', 's4')
    net.addLink('s4', 's5')
    net.addLink('s4', 's6')
    net.addLink('h1', 's1')
    net.addLink('s5', 'h2')
    net.addLink('s6', 'h3')

    net.build()
    net.start()
    CLI(net)

    net.stop()


if __name__ == "__main__":
    main() 
