#!/usr/bin/env python

import threading
import redis
import time


fetch_counter_script = \
'''
local counters_db = "2"
local config_db = "4"

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

class CounterPollingThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = "CounterPolling"
        self.task_stopping_event = threading.Event()
        self.redis = redis.Redis(host='localhost', db=2)
        self.sha = self.redis.script_load(fetch_counter_script)

    def signal_handler(self, sig, frame):
        if sig == signal.SIGINT:
            self.task_stopping_event.set()
        elif sig == signal.SIGTERM:
            self.task_stopping_event.set()

    def run(self):
        global counters
        while not self.task_stopping_event.is_set():
            counters.append(self.redis.evalsha(self.sha, 0))
            if len(counters) > 50:
                counters.remove(counters[0])
            time.sleep(0.2)

    def join(self):
        self.task_stopping_event.set()
        threading.Thread.join(self)


def fetch_counter_for_port(allport_counters, portoid):
    for counter in allport_counters:
        if 'COUNTERS:' + portoid == counter[1]:
            return counter
    
cpt = CounterPollingThread()
cpt.start()

r = redis.Redis(host='localhost', db=2)
sha = r.script_load(fetch_qid_pid_map_script)
qid_pid_list = r.evalsha(sha, 0)
qid2pid = dict(list(zip(qid_pid_list[0::2], qid_pid_list[1::2])))

ps = r.pubsub()
ps.subscribe('PFC_WD_ACTION')
it = ps.listen()

history_counters = []
for i in it:
    # {'pattern': None, 'type': 'message', 'channel': 'PFC_WD_ACTION', 'data': '["oid:0x1500000000080e","storm"]'}
    if not i:
        continue
    data = i.get('data')
    if not isinstance(data, (str)):
        continue
    items = data[1:-1].split(',')
    if 'storm' == items[1][1:-1]:
        portoid = qid2pid[items[0][1:-1]]
        counters_snapshot = counters[:]
        for allport_counters in counters_snapshot:
            history_counters.append(fetch_counter_for_port(allport_counters, portoid))

        history_counters.append(fetch_counter_for_port(counters[-1], portoid))
        print('Historical counters {}'.format(history_counters))
        history_counters = []
