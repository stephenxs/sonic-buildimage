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

fetch_port_counter_script = \
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

fetch_queue_counnter_script = \
'''
local counters_db = "2"

local queueoidmap = {}
local result = {}

redis.call('SELECT', counters_db)

-- Generate queues
local queuesinfo = redis.call('HGETALL', 'COUNTERS_QUEUE_NAME_MAP')
for i = 1, #queuesinfo, 2 do
    local queue = string.sub(queuesinfo[i], -2)
    if queue == ":3" or queue == ":4" then
        local queue_counter = redis.call('HMGET', 'COUNTERS:' .. queuesinfo[i+1], 'SAI_QUEUE_STAT_PACKETS', 'SAI_QUEUE_STAT_CURR_OCCUPANCY_BYTES')
        table.insert(result, {queuesinfo[i+1], tostring(queue_counter[1]) .. ',' .. tostring(queue_counter[2])})
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


def fetch_counter_for_queue(allqueue_counters, queueoid):
    for counter in allqueue_counters:
        if queueoid == counter[0]:
            return counter
    return None


r = redis.Redis(host='localhost', db=2)
qid_pid_map_sha = r.script_load(fetch_qid_pid_map_script)
qid_pid_list = r.evalsha(qid_pid_map_sha, 0)
qid2pid = dict(list(zip(qid_pid_list[0::2], qid_pid_list[1::2])))

fetch_port_counter_sha = r.script_load(fetch_port_counter_script)
fetch_queue_counter_sha = r.script_load(fetch_queue_counnter_script)

ps = r.pubsub()
ps.subscribe('PFC_WD_ACTION')

while True:
    counters.append((r.evalsha(fetch_port_counter_sha, 0), r.evalsha(fetch_queue_counter_sha, 0), time.ctime(), time.time()))
    if len(counters) > 50:
        counters.pop(0)
    notification = ps.get_message()
    if notification:
        data = notification.get('data')
        if isinstance(data, (str)):
            items = data[1:-1].split(',')
            if 'storm' == items[1][1:-1]:
                history_port_counters = []
                history_queue_counters = []
                try:
                    queueoid = items[0][1:-1]
                    portoid = qid2pid[queueoid]
                    for all_counters in counters:
                        allport_counters, allqueue_counters, wallclock, timestamp = all_counters
                        counter_info = fetch_counter_for_port(allport_counters, portoid)
                        if counter_info:
                            if len(history_port_counters) == 0:
                                # Insert "start" timestamp
                                history_port_counters.append(wallclock)
                                history_port_counters.append(counter_info[0])
                                history_port_counters.append((timestamp, counter_info[1]))
                            history_port_counters.append((timestamp, counter_info[2]))
                        counter_info = fetch_counter_for_queue(allqueue_counters, queueoid)
                        if counter_info:
                            if len(history_queue_counters) == 0:
                                # Insert "start" wallclock
                                history_queue_counters.append(wallclock)
                                history_queue_counters.append((timestamp, counter_info[0]))
                            history_queue_counters.append((timestamp, counter_info[1]))
                    # Insert "end" wallclock
                    history_port_counters.append(wallclock)
                    history_queue_counters.append(wallclock)
                finally:
                    log_notice('Historical port counters {}'.format(history_port_counters))
                    log_notice('Historical queue counters {}'.format(history_queue_counters))

    time.sleep(0.2)
