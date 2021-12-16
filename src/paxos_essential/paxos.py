import rospy
import uuid
from paxos_essential.msg import *
from threading import Lock
from time import time, sleep
from paxos_essential.proposer import Proposer
from paxos_essential.acceptor import Acceptor
from paxos_essential.learner import Learner


class PaxosRSM():
    def __init__(self, init_state, transitions, leader=False):
        self.uid = str(uuid.uuid4())
        self.state = init_state
        self.transitions = [lambda x: (x, True)] + transitions
        self.current_instance = -1
        self.finished_instance = -1
        self.proposers = {}
        self.acceptors = {}
        self.learners = {}
        self.cached_values = {}
        self.running_instances = {}
        self.request_history = {}
        self.lock = Lock()

        self.leader = leader
        self.acquiring = False
        self.leader_proposal_id = (0, self.uid) if leader else (-1, '')
        self.tick_period = rospy.get_param('tick_period')
        self.live_window = rospy.get_param('live_window')
        self.last_tick = time()
        self.last_prep = time()

        self.tick_pub = rospy.Publisher('tick', Tick, queue_size=10)
        self.prepare_pub = rospy.Publisher('prepare', Prepare, queue_size=10)
        self.promise_pub = rospy.Publisher('promise', Promise, queue_size=10)
        self.refuse_prepare_pub = rospy.Publisher('refuse_prepare', Refusal, queue_size=10)
        self.accept_pub = rospy.Publisher('accept', Accept, queue_size=10)
        self.refuse_accept_pub = rospy.Publisher('refuse_accept', Refusal, queue_size=10)
        self.accepted_pub = rospy.Publisher('accepted', Accepted, queue_size=10)
        self.finalized_pub = rospy.Publisher('finalized', Finalized, queue_size=10)
        self.client_response_pub = rospy.Publisher('client_response', ClientResponse, queue_size=10)

        self.client_request_sub = rospy.Subscriber('client_request', ClientRequest, self.handle_client_request)
        self.tick_sub = rospy.Subscriber('tick', Tick, self.handle_tick)
        self.prepare_sub = rospy.Subscriber('prepare', Prepare, self.handle_prepare)
        self.promise_sub = rospy.Subscriber('promise', Promise, self.handle_promise)
        self.refuse_prepare_sub = rospy.Subscriber('refuse_prepare', Refusal, self.handle_refuse_prepare)
        self.accept_sub = rospy.Subscriber('accept', Accept, self.handle_accept)
        self.accepted_sub = rospy.Subscriber('accepted', Accepted, self.handle_accepted)
        self.finalized_sub = rospy.Subscriber('finalized', Finalized, self.handle_finalized)

    def run(self):
        rospy.loginfo(f'{rospy.get_name()} started, uid={self.uid}, leader={str(self.leader)}')
        i = 0
        while not rospy.is_shutdown():
            if self.leader:
                self.tick()
            sleep(self.tick_period)
            i += self.tick_period
            if i >= self.live_window:
                self.check_leader()
                if self.leader:
                    self.broadcast_results()
                i = 0

    def tick(self):
        proposal_num, proposer_id = self.leader_proposal_id
        self.tick_pub.publish(
            instance=self.finished_instance,
            proposal_num=proposal_num,
            proposer_id=proposer_id
        )

    def check_leader(self):
        if (time() - self.last_tick > self.live_window and
            time() - self.last_prep > self.live_window * 1.5):
            if not self.acquiring:
                self.new_instance()
                self.acquiring = True
            self.proposers[self.current_instance].prepare(self.current_instance)

    def broadcast_results(self):
        for instance in range(self.current_instance + 1):
            if self.learners[instance].complete:
                self.finalized_pub.publish(
                    instance=instance, value=self.learners[instance].final_value
                )

    def new_instance(self, instance=None):
        with self.lock:
            if instance is None:
                self.current_instance += 1
            else:
                self.current_instance = max(instance, self.current_instance)
            self.proposers[self.current_instance] = Proposer(
                self.uid, self.leader, self.prepare_pub, self.accept_pub
            )
            self.acceptors[self.current_instance] = Acceptor(
                self.uid, self.promise_pub, self.accepted_pub, self.refuse_prepare_pub
            )
            self.learners[self.current_instance] = Learner(
                self.uid, self.accepted_pub, self.finalized_pub
            )

    def handle_client_request(self, client_request):
        rospy.loginfo('request received')
        request = (client_request.client_id, client_request.request_id)
        if request not in self.request_history:
            self.new_instance()
            self.running_instances[self.current_instance] = \
                request + (client_request.value,)
            self.request_history[request] = self.current_instance
        if self.leader:
            self.proposers[self.request_history[request]].prepare(
                self.current_instance, client_request.value
            )

    def handle_tick(self, tick):
        proposal_id = (tick.proposal_num, tick.proposer_id)
        if proposal_id >= self.leader_proposal_id:
            self.last_tick = time()
            self.acquiring = False
            if proposal_id > self.leader_proposal_id:
                self.leader_proposal_id = proposal_id
                if self.leader and tick.proposer_id != self.uid:
                    self.leader = False
                    rospy.loginfo(f'{rospy.get_name()} lost leadership to {tick.proposer_id}')

    def handle_prepare(self, prepare):
        if prepare.proposer_id != self.uid:
            self.last_prep = time()
        if prepare.instance not in self.proposers:
            self.new_instance(prepare.instance)
        self.proposers[prepare.instance].observe_proposal(
            prepare.proposal_num, prepare.proposer_id
        )
        self.acceptors[prepare.instance].handle_prepare(prepare)

    def handle_promise(self, promise):
        if promise.instance not in self.proposers:
            self.new_instance(promise.instance)
        self.proposers[promise.instance].handle_promise(promise)
        if not self.leader and self.proposers[promise.instance].leader:
            rospy.loginfo(f'{rospy.get_name()} acquired leadership at instance {promise.instance}')
            self.leader = True
            self.acquiring = False
            self.leader_proposal_id = self.proposers[promise.instance].proposal_id
            self.tick()
            for instance, value in self.running_instances:
                self.proposers[instance].leader = True
                self.proposers[instance].prepare(instance, value)

    def handle_refuse_prepare(self, refuse_prepare):
        self.proposers[refuse_prepare.instance].observe_proposal(
            refuse_prepare.proposal_num, refuse_prepare.proposer_id
        )

    def handle_accept(self, accept):
        if accept.instance not in self.acceptors:
            self.new_instance(accept.instance)
        self.acceptors[accept.instance].handle_accept(accept)

    def handle_accepted(self, accepted):
        if self.leader:
            self.learners[accepted.instance].handle_accepted(accepted)

    def handle_finalized(self, finalized):
        if finalized.instance not in self.learners:
            self.new_instance(finalized.instance)
        if finalized.instance <= self.finished_instance:
            return
        self.learners[finalized.instance].final_value = finalized.value
        if self.running_instances.get(finalized.instance) is not None:
            client_id, request_id, value = self.running_instances.pop(finalized.instance)
        else:
            client_id, request_id = None, None
        self.cached_values[finalized.instance] = (client_id, request_id, finalized.value)
        rospy.loginfo(f'{rospy.get_name()} cached value {finalized.value} '
                        f'for instance {finalized.instance}')
        while self.finished_instance + 1 in self.cached_values:
            self.finished_instance += 1
            client_id, request_id, value = self.cached_values.pop(self.finished_instance)
            self.state, output = self.transitions[value](self.state)
            if client_id is not None and self.leader:
                self.client_response_pub.publish(
                    client_id=client_id, request_id=request_id,
                    value=value, success=output
                )
            rospy.loginfo(f'{rospy.get_name()} executed value {value} '
                          f'for instance {self.finished_instance}')
