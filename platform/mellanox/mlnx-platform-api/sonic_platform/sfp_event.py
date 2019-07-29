#!/usr/bin/env python
'''
listen to the SDK for the SFP change event and return to chassis.
'''

from __future__ import print_function
import sys, errno
import os
import time
import select
from python_sdk_api.sx_api import *
from sonic_daemon_base.daemon_base import Logger

SYSLOG_IDENTIFIER = "sfp-event"

SDK_SFP_STATE_IN = 0x1
SDK_SFP_STATE_OUT = 0x2
STATUS_PLUGIN = '1'
STATUS_PLUGOUT = '0'
STATUS_UNKNOWN = '2'

sfp_value_status_dict = {
        SDK_SFP_STATE_IN:  STATUS_PLUGIN,
        SDK_SFP_STATE_OUT: STATUS_PLUGOUT,
}

PMPE_PACKET_SIZE = 2000

logger = Logger(SYSLOG_IDENTIFIER)

class sfp_event:
    ''' Listen to plugin/plugout cable events '''

    SX_OPEN_RETRIES = 20

    def __init__(self):
        self.swid = 0
        self.handle = None

    def initialize(self):
        # open SDK API handle.
        # retry at most SX_OPEN_RETRIES times to wait until SDK is started during system startup
        retry = 1
        while True:
            rc, self.handle = sx_api_open(None)
            if rc == SX_STATUS_SUCCESS:
                break

            logger.log_info("failed to open SDK API handle... retrying {}".format(retry))

            time.sleep(2 ** retry)
            retry += 1

            if retry > self.SX_OPEN_RETRIES:
                raise RuntimeError("failed to open SDK API handle after {} retries".format(retry))

        # Allocate SDK fd and user channel structures
        self.rx_fd_p = new_sx_fd_t_p()
        self.user_channel_p = new_sx_user_channel_t_p()

        rc = sx_api_host_ifc_open(self.handle, self.rx_fd_p)
        if rc != SX_STATUS_SUCCESS:
            raise RuntimeError("sx_api_host_ifc_open exited with error, rc {}".format(rc))

        self.user_channel_p.type = SX_USER_CHANNEL_TYPE_FD
        self.user_channel_p.channel.fd = self.rx_fd_p

        rc = sx_api_host_ifc_trap_id_register_set(self.handle,
                                                  SX_ACCESS_CMD_REGISTER,
                                                  self.swid,
                                                  SX_TRAP_ID_PMPE,
                                                  self.user_channel_p)
        if rc != SX_STATUS_SUCCESS:
            raise RuntimeError("sx_api_host_ifc_trap_id_register_set exited with error, rc {}".format(rc))

    def deinitialize(self):
        if self.handle is None:
            return

        # unregister trap id
        rc = sx_api_host_ifc_trap_id_register_set(self.handle,
                                                  SX_ACCESS_CMD_DEREGISTER,
                                                  self.swid,
                                                  SX_TRAP_ID_PMPE,
                                                  self.user_channel_p)
        if rc != SX_STATUS_SUCCESS:
            logger.log_error("sx_api_host_ifc_trap_id_register_set exited with error, rc {}".format(rc))

        rc = sx_api_host_ifc_close(self.handle, self.rx_fd_p)
        if rc != SX_STATUS_SUCCESS:
            logger.log_error("sx_api_host_ifc_close exited with error, rc {}".format(rc))

        rc = sx_api_close(self.handle)
        if rc != SX_STATUS_SUCCESS:
            logger.log_error("sx_api_close exited with error, rc {}".format(rc))

        delete_sx_fd_t_p(self.rx_fd_p)
        delete_sx_user_channel_t_p(self.user_channel_p)

    def check_sfp_status(self, port_change, timeout):
        """
        the meaning of timeout is aligned with select.select, which has the following meaning:
            0: poll, returns without blocked
            arbitrary positive value: doesn't returns until at least fd in the set is ready or
                                        <timeout> seconds elapsed
        Note:
            check_sfp_status makes the use of select to retrieve the notifications, which means
            it should has the logic of reading out all the notifications in the fd selected without blocked.
            However, it fails to do that due to some sdk API's characteristics:
                sx_lib_host_ifc_recv can only read one notification each time and will block when no notification in that fd.
                sx_lib_host_ifc_recv_list can return all notification in the fd via a single reading operation but
                                         not supported by PMPE register (I've tested it but failed)
            as a result the only way to satisfy the logic is to call sx_lib_host_ifc_recv in a loop until all notifications
            has been read and we have to find a way to check that. it seems the only way to check that is via using select. 
            in this sense, we return one notification each time check_sfp_status called and let the caller, get_change_event,
            to repeat calling it with timeout = 0 in a loop until no new notification read (in this case it returns false).
            by doing so all the notifications in the fd can be retrieved through a single call to get_change_event.
        """
        found = 0

        try:
            read, _, _ = select.select([self.rx_fd_p.fd], [], [], timeout)
        except select.error as err:
            rc, msg = err
            if rc == errno.EAGAIN or rc == errno.EINTR:
                return False
            else:
                raise

        for fd in read:
            if fd == self.rx_fd_p.fd:
                success, port_list, module_state = self.on_pmpe(self.rx_fd_p)
                if not success:
                    logger.log_error("failed to read from {}".format(fd))
                    break

                sfp_state = sfp_value_status_dict.get(module_state, STATUS_UNKNOWN)
                if sfp_state == STATUS_UNKNOWN:
                    # in the following sequence, STATUS_UNKNOWN can be returned.
                    # so we shouldn't raise exception here.
                    # 1. some sfp module is inserted
                    # 2. sfp_event gets stuck and fails to fetch the change event instantaneously
                    # 3. and then the sfp module is removed
                    # 4. sfp_event starts to try fetching the change event
                    # in this case found is increased so that True will be returned
                    logger.log_info("unknown module state {}, maybe the port suffers two adjacent insertion/removal".format(module_state))
                    found += 1
                    continue

                for port in port_list:
                    logger.log_info("SFP on port {} state {}".format(port, sfp_state))
                    port_change[port] = sfp_state
                    found += 1

        if found == 0:
            return False
        else:
            return True

    def on_pmpe(self, fd_p):
        ''' on port module plug event handler '''

        # recv parameters
        pkt_size = PMPE_PACKET_SIZE
        pkt_size_p = new_uint32_t_p()
        uint32_t_p_assign(pkt_size_p, pkt_size)
        pkt = new_uint8_t_arr(pkt_size)
        recv_info_p = new_sx_receive_info_t_p()
        pmpe_t = sx_event_pmpe_t()
        port_attributes_list = new_sx_port_attributes_t_arr(64)
        port_cnt_p = new_uint32_t_p()
        uint32_t_p_assign(port_cnt_p,64)
        label_port_list = []
        module_state = 0

        rc = sx_lib_host_ifc_recv(fd_p, pkt, pkt_size_p, recv_info_p)
        if rc != 0:
            logger.log_error("sx_lib_host_ifc_recv exited with error, rc %d" % rc)
            status = False
        else:
            status = True
            pmpe_t = recv_info_p.event_info.pmpe
            port_list_size = pmpe_t.list_size
            logical_port_list = pmpe_t.log_port_list
            module_state = pmpe_t.module_state

            for i in xrange(port_list_size):
                logical_port = sx_port_log_id_t_arr_getitem(logical_port_list, i)
                rc = sx_api_port_device_get(self.handle, 1 , 0, port_attributes_list,  port_cnt_p)
                port_cnt = uint32_t_p_value(port_cnt_p)

                for i in xrange(port_cnt):
                    port_attributes = sx_port_attributes_t_arr_getitem(port_attributes_list,i)
                    if port_attributes.log_port == logical_port:
                        lable_port = port_attributes.port_mapping.module_port
                        break
                label_port_list.append(lable_port)

        delete_uint32_t_p(pkt_size_p)
        delete_uint8_t_arr(pkt)
        delete_sx_receive_info_t_p(recv_info_p)
        delete_sx_port_attributes_t_arr(port_attributes_list)
        delete_uint32_t_p(port_cnt_p)

        return status, label_port_list, module_state,
