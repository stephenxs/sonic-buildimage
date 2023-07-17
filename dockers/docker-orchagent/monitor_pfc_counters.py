#!/usr/bin/env python

import threading
import redis
import time
import syslog
import logging 

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
logger.addHandler(logging.NullHandler())

SYSLOG_IDENTIFIER = 'monitor_pfc_counters'

def log_notice(msg):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_NOTICE, msg)
    syslog.closelog()

fetch_counter_script = \
'''
local counters_db = "2"

local portoidmap = {}
local result = {}

redis.call('SELECT', counters_db)

-- Generate ports
local portsinfo = redis.call('HGETALL', 'COUNTERS_PORT_NAME_MAP')
for i = 1 , #portsinfo, 2 do
    local port = portsinfo[i]
    portoidmap[port] = 'COUNTERS:' .. portsinfo[i+1]
end

for port in pairs(portoidmap) do
    local pfc_counter = redis.call('HMGET', portoidmap[port], 'SAI_PORT_STAT_PFC_3_RX_PAUSE_DURATION_US', 'SAI_PORT_STAT_PFC_4_RX_PAUSE_DURATION_US')
    if pfc_counter[1] or pfc_counter[2] then
        table.insert(result, {port, portoidmap[port], tostring(pfc_counter[1]) .. ',' .. tostring(pfc_counter[2])})
    end
end

return result

'''

fetch_qid_pid_map_script = \
'''
local counters_db = "2"

redis.call('SELECT', counters_db)

local qid2pid = redis.call('HGETALL', 'COUNTERS_QUEUE_PORT_MAP')

return qid2pid
'''

counters = []


def fetch_counter_for_port(allport_counters, portoid):
    for counter in allport_counters:
        if 'COUNTERS:' + portoid == counter[1]:
            return counter
    return None
    

r = redis.Redis(host='localhost', db=2)
qid_pid_map_sha = r.script_load(fetch_qid_pid_map_script)
qid_pid_list = r.evalsha(qid_pid_map_sha, 0)
qid2pid = dict(list(zip(qid_pid_list[0::2], qid_pid_list[1::2])))

fetch_counter_sha = r.script_load(fetch_counter_script)

ps = r.pubsub()
ps.subscribe('PFC_WD_ACTION')

while True:
    counters.append(r.evalsha(fetch_counter_sha, 0))
    if len(counters) > 50:
        counters.pop(0)
    notification = ps.get_message()
    if notification:
        data = notification.get('data')
        if isinstance(data, (str)):
            items = data[1:-1].split(',')
            if 'storm' == items[1][1:-1]:
                history_counters = []
                try:
                    portoid = qid2pid[items[0][1:-1]]
                    counters_snapshot = counters[:]
                    for allport_counters in counters:
                        counter_info = fetch_counter_for_port(allport_counters, portoid)
                        if counter_info:
                            if len(history_counters) == 0:
                                history_counters.append(counter_info[0])
                                history_counters.append(counter_info[1])
                            history_counters.append(counter_info[2])

                finally:
                    log_notice('Historical counters {}'.format(history_counters))

    time.sleep(0.2)
