#!/usr/bin/env python
#
# Written by Pavel Chjen
# Main code taken from add_vn_nic_to_dvs.py 
# GitHub: https://github.com/pavelchjen
# Email: pavel.chjen@gmail.com
# 
#
# Note: Example code For testing purposes only
#
# This code has been released under the terms of the Apache-2.0 license
# http://opensource.org/licenses/Apache-2.0
#

import requests
from tools import cli, service_instance, pchelper, tasks
from pyVmomi import vim


# disable  urllib3 warnings
requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning)


def update_virtual_nic_group(si, vm_obj, nic_number, port):
    """
    :param si: Service Instance
    :param vm_obj: Virtual Machine Object
    :param nic_number: Network Interface Controller Number
    :param new_nic_state: Either Connect, Disconnect or Delete
    :return: True if success
    """
    nic_prefix_label = 'Network adapter '
    nic_label = nic_prefix_label + str(nic_number)
    virtual_nic_device = None
    for dev in vm_obj.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualEthernetCard) \
                and dev.deviceInfo.label == nic_label:
            virtual_nic_device = dev
    if not virtual_nic_device:
        raise RuntimeError('Virtual {} could not be found.'.format(nic_label))

    virtual_nic_spec = vim.vm.device.VirtualDeviceSpec()
    virtual_nic_spec.operation = \
        vim.vm.device.VirtualDeviceSpec.Operation.edit
    virtual_nic_spec.device = virtual_nic_device
    virtual_nic_spec.device.key = virtual_nic_device.key
    virtual_nic_spec.device.macAddress = virtual_nic_device.macAddress
    virtual_nic_spec.device.backing = \
        vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
    virtual_nic_spec.device.backing.port = vim.dvs.PortConnection()
    virtual_nic_spec.device.backing.port.portgroupKey = port.portgroupKey
    virtual_nic_spec.device.backing.port.switchUuid = port.dvsUuid
    virtual_nic_spec.device.backing.port.portKey = port.key
    
    virtual_nic_spec.device.backing = virtual_nic_device.backing
    #virtual_nic_spec.device.wakeOnLanEnabled = \
    #    virtual_nic_device.wakeOnLanEnabled
    #virtual_nic_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
    dev_changes = [virtual_nic_spec]
    spec = vim.vm.ConfigSpec()
    spec.deviceChange = dev_changes
    task = vm_obj.ReconfigVM_Task(spec=spec)
    tasks.wait_for_tasks(si, [task])
    return True


def search_port(dvs, portgroupkey):
    """
    Find port by port group key
    """
    search_portkey = []
    criteria = vim.dvs.PortCriteria()
    criteria.connected = False
    criteria.inside = True
    criteria.portgroupKey = portgroupkey
    ports = dvs.FetchDVPorts(criteria)
    for port in ports:
        search_portkey.append(port.key)
    print(search_portkey)
    return search_portkey[0]


def port_find(dvs, key):
    """
    Find port by port key
    """
    obj = None
    ports = dvs.FetchDVPorts()
    for port in ports:
        if port.key == key:
            obj = port
    return obj

def main():
    parser = cli.Parser()
    parser.add_required_arguments(cli.Argument.VM_NAME, cli.Argument.PORT_GROUP)
    parser.add_custom_argument('--nicnumber', required=True, help='NIC number.', type=int)
    args = parser.get_args()
    si = service_instance.connect(args)
    content = si.RetrieveContent()
    print("Search VDS PortGroup by Name ...")
    portgroup = pchelper.get_obj(content, [vim.dvs.DistributedVirtualPortgroup], args.port_group)
    if portgroup is None:
        print("Portgroup not Found in DVS ...")
        sys.exit(0)
    print("Search Available(Unused) port for VM...")
    dvs = portgroup.config.distributedVirtualSwitch
    port_key = search_port(dvs, portgroup.key)
    port = port_find(dvs, port_key)
    print('Searching for VM {}'.format(args.vm_name))
    vm_obj = pchelper.get_obj(content, [vim.VirtualMachine], args.vm_name)

    if vm_obj:
        update_virtual_nic_group(si, vm_obj, args.nicnumber, port)
        print('VM NIC {} port-group successfully changed to {}'.format(args.nicnumber, args.port_group))
    else:
        print("VM not found")


# start
if __name__ == "__main__":
    main()
