import rospy
import uuid
from paxos_essential.msg import *
from sched import scheduler
from time import time


class Proposer():
    def __init__(self, uid, instance, leader, prepare_pub, accept_pub):
        self.uid = uid
        self.instance = instance
        self.leader = leader
        self.prepare_pub = prepare_pub
        self.accept_pub = accept_pub

        self.majority = rospy.get_param('majority')
        self.proposal_num = -1
        self.proposed_value = None
        self.promise_received = set()
        self.max_accepted_proposal_id = None

    def observe_proposal(self, proposal_num, proposer_id):
        proposal_id = (proposal_num, proposer_id)
        if proposal_id >= (self.proposal_num, self.uid):
            self.proposal_num = proposal_num

    def prepare(self, proposed_value=None):
        self.promise_received = set()
        self.proposal_num += 1
        self.proposal_id = (self.proposal_num, self.uid)
        if self.leader:
            self.proposed_value = proposed_value
            self.accept_pub.publish(
                instance=self.instance,
                proposal_num=self.proposal_num,
                proposer_id=self.uid,
                proposed_value=proposed_value
            )
        else:
            self.prepare_pub.publish(
                instance=self.instance,
                proposal_num=self.proposal_num,
                proposer_id=self.uid
            )

    def handle_promise(self, promise):
        self.observe_proposal(promise.proposal_num, promise.proposer_id)

        proposal_id = (promise.proposal_num, promise.proposer_id)
        # promise not for the current proposal
        if proposal_id != self.proposal_id:
            return
        # promise already received
        if promise.acceptor_id in self.promise_received:
            return

        self.promise_received.add(promise.acceptor_id)
        accepted_proposal_id = (promise.accepted_proposal_num, promise.accepted_proposer_id)
        if accepted_proposal_id > self.max_accepted_proposal_id:
            self.max_accepted_proposal_id = accepted_proposal_id
            self.proposed_value = promise.accepted_value

        if len(self.promise_received) == self.majority:
            if self.proposed_value is not None:
                self.accept_pub.publish(
                    instance=self.instance,
                    proposal_num=promise.proposal_num,
                    proposer_id=promise.proposer_id,
                    proposed_value=self.proposed_value
                )
            else:
                self.leader = True


class Acceptor():
    def __init__(self, uid, instance, accepted_pub, refuse_prepare_pub, refuse_accept_pub):
        self.uid = uid
        self.instance = instance
        self.accepted_pub = accepted_pub
        self.refuse_prepare_pub = refuse_prepare_pub
        self.refuse_accept_pub = refuse_accept_pub

        self.promised_id = None
        self.accepted_proposal_num = None
        self.accepted_proposer_id = None
        self.accepted_value = None

    def handle_prepare(self, prepare):
        proposal_id = (prepare.proposal_num, prepare.proposer_id)
        if proposal_id > self.promised_id:
            self.promised_id = proposal_id
            self.promise_pub.publish(
                instance=prepare.instance,
                proposal_num=prepare.proposal_num,
                proposer_id=prepare.proposer_id,
                acceptor_id=self.uid,
                accepted_proposal_num=self.accepted_proposal_num,
                accepted_proposer_id=self.accepted_proposer_id,
                accepted_value=self.accepted_value
            )
        else:
            promised_proposal_num, promised_proposer_id = self.promised_id
            self.refuse_prepare.publish(
                instance=prepare.instance,
                promised_proposal_num=promised_proposal_num,
                promised_proposer_id=promised_proposer_id
            )

    def handle_accept(self, accept):
        proposal_id = (accept.proposal_num, accept.proposer_id)
        if proposal_id >= self.promised_id:
            self.promised_id = proposal_id
            self.accepted_proposal_num, self.accepted_proposer_id = proposal_id
            self.accepted_value = accept.proposed_value
            self.accepted_pub.publish(
                instance=accept.instance,
                acceptor_id=self.uid,
                proposal_num=self.accepted_proposal_num,
                proposal_id=self.accepted_proposer_id,
                accepted_value=self.accepted_value
            )
        else:
            promised_proposal_num, promised_proposer_id = self.promised_id
            self.refuse_accept.publish(
                instance=accept.instance,
                promised_proposal_num=promised_proposal_num,
                promised_proposer_id=promised_proposer_id
            )


class Learner():
    def __init__(self, uid, instance, finalized_pub):
        self.uid = uid
        self.instance = instance
        self.majority = rospy.get_param('majority')
        self.proposal_counts = {} # proposal_id -> [acceptor_ids, accepted_value]
        self.accepted_proposals = {} # acceptor_id -> proposal_id
        self.final_acceptors = set()
        self.final_value = None
        self.finalized_pub = finalized_pub

    @property
    def complete(self):
        return self.final_value is not None

    def handle_accepted(self, accepted):
        if self.final_value is not None:
            if accepted.accepted_value == self.final_value:
                self.final_acceptors.add(accepted.acceptor_id)
            return

        proposal_id = (accepted.proposal_num, accepted.proposer_id)
        accepted_proposal_id = self.accepted_proposals.get(accepted.acceptor_pid)
        if accepted_proposal_id >= proposal_id:
            return

        self.accepted_proposals[accepted.acceptor_pid] = proposal_id
        if accepted_proposal_id is not None:
            self.proposal_counts[accepted_proposal_id][0].remove(accepted.acceptor_id)
        if proposal_id not in self.proposal_counts:
            self.proposal_counts[proposal_id] = [set(), accepted.accepted_value]
        self.proposal_counts[proposal_id][0].add(accepted.acceptor_id)

        if len(self.proposal_counts[proposal_id][0]) == self.majority:
            self.final_acceptors, self.final_value = self.proposal_counts[proposal_id]
            self.proposal_counts = None
            self.accepted_proposals = None
            self.finalized_pub.publish(instance=self.instance, value=self.final_value)


class PaxosRSM():
    def __init__(self, init_state, transitions, leader=False):
        self.uid = str(uuid.uuid4())
        self.state = init_state
        self.transitions = transitions
        self.current_instance = -1
        self.instance_to_exe = 0
        self.proposers = {}
        self.acceptors = {}
        self.learners = {}
        self.executed_values = {}
        self.cached_values = {}
        self.running_instances = {}

        self.tick_pub = rospy.Publisher('tick', Tick, queue_size=10)
        self.prepare_pub = rospy.Publisher('prepare', Prepare, queue_size=10)
        self.promise_pub = rospy.Publisher('promise', Promise, queue_size=10)
        self.refuse_prepare_pub = rospy.Publisher('refuse_prepare', Refusal, queue_size=10)
        self.accept_pub = rospy.Publisher('accept', Accept, queue_size=10)
        self.refuse_accept_pub = rospy.Publisher('refuse_accept', Refusal, queue_size=10)
        self.accepted_pub = rospy.Publisher('accepted', Accepted, queue_size=10)
        self.finalized_pub = rospy.Publisher('finalized', Finalized, queue_size=10)
        self.client_response_pub = rospy.Publisher('client_reponse', ClientResponse, queue_size=10)

        self.client_request_sub = rospy.Subscriber('client_request', ClientRequest, self.handle_client_request)
        self.tick_sub = rospy.Subscriber('tick', Tick, self.handle_tick)
        self.prepare_sub = rospy.Subscriber('prepare', Prepare, self.handle_prepare)
        self.promise_sub = rospy.Subscriber('promise', Promise, self.handle_promise)
        self.refuse_prepare_sub = rospy.Subscriber('refuse_prepare', Refusal, self.handle_refuse_prepare)
        self.accept_sub = rospy.Subscriber('accept', Accept, self.handle_accept)
        self.refuse_accept_sub = rospy.Subscriber('refuse_accept', Refusal, self.handle_refuse_accept)
        self.accepted_sub = rospy.Subscriber('accepted', Accepted, self.handle_accepted)
        self.finalized_sub = rospy.Subscriber('finalized', Finalized, self.handle_finalized)

        self.leader = leader
        self.leader_proposal_id = None
        self.tick_period = rospy.get_param('tick_period')
        self.live_window = rospy.get_param('live_window')
        self.last_tick = time()
        self.last_prep = time()
        self.refusals = {}
        if leader:
            self.leader_proposal_id = (0, self.uid)
            self.tick()
        self.check_leader()

    def tick(self):
        proposal_num, proposer_id = self.leader_proposal_id
        self.tick_pub.publish(proposal_num=proposal_num, proposer_id=proposer_id)
        s = scheduler(time)
        s.enter(self.tick_period, 1, self.tick)

    def check_leader(self):
        if not self.leader_alive() and not self.recent_prepare():
            self.refusals[self.current_instance] = 0
            self.get_proposer(self.current_instance).prepare()
        s = scheduler(time)
        s.enter(self.live_window, 2, self.check_leader)

    def leader_alive(self):
        return time() - self.last_tick <= self.live_window

    def recent_prepare(self):
        return time() - self.last_prep <= self.live_window * 1.5

    def handle_tick(self, proposal_num, proposer_id):
        proposal_id = (proposal_num, proposer_id)
        if proposal_id >= self.leader_proposal_id:
            self.last_tick = time()
            if proposal_id > self.leader_proposal_id:
                self.leader_proposal_id = proposal_id
                if self.leader and proposer_id != self.uid:
                    self.leader = False

    def get_proposer(self, instance):
        if self.proposers.get(instance) is None:
            self.proposers[instance] = Proposer(self.uid, instance, self.prepare_pub, self.accept_pub)
        return self.proposers[instance]

    def get_acceptor(self, instance):
        if self.acceptors.get(instance) is None:
            self.acceptors[instance] = Acceptor(
                self.uid, instance, self.accept_pub, self.refuse_prepare_pub, self.refuse_accept_pub
            )
        return self.acceptors[instance]

    def get_learner(self, instance):
        if self.learners.get(instance) is None:
            self.learners[instance] = Learner(self.uid, instance, self.finalized_pub)
        return self.learners[instance]

    def handle_client_request(self, client_request):
        self.current_instance += 1
        self.running_instances[self.current_instance] = (client_request.client_id, client_request.value)
        if self.leader:
            self.refusals[self.current_instance] = 0
            self.get_proposer(self.current_instance).prepare(client_request.value)

    def handle_prepare(self, prepare):
        if prepare.proposer_id != self.uid:
            self.last_prep = time()
        self.get_proposer(prepare.instance).observe_proposal(prepare.proposal_num, prepare.proposer_id)
        self.get_acceptor(prepare.instance).handle_prepare(prepare)

    def handle_promise(self, promise):
        proposer = self.get_proposer(promise.instance)
        proposer.handle_promise(promise)
        if not self.leader and proposer.leader:
            self.leader = True
            self.leader_proposal_id = proposer.proposal_id
            self.tick()
            self.leadership_acquired()

    def handle_refuse_prepare(self, refuse_prepare):
        self.get_proposer(refuse_prepare.instance).observe_proposal(
            refuse_prepare.proposal_num, refuse_prepare.proposer_id
        )

    def handle_accept(self, accept):
        self.get_acceptor(accept.instance).handle_accept(accept)

    def handle_refuse_accept(self, refuse_accept):
        proposal_id = (refuse_accept.proposal_num, refuse_accept.proposed_id)
        if proposal_id == self.get_proposer(refuse_accept.instance).proposal_id:
            self.refusals[refuse_accept.instance] += 1
            if self.leader and self.refusals[refuse_accept.instance] >= self.majority:
                self.leader = False
                self.leader_proposal_id = None

    def handle_accepted(self, accepted):
        if self.leader:
            self.get_learner(accepted.instance).handle_accepted(accepted)

    def handle_finalized(self, finalized):
        self.get_learner(finalized.instance).final_value = finalized.value
        client_id, value = self.running_instances.pop(finalized.instance)
        self.cached_values[finalized.instance] = (client_id, finalized.value)
        while self.instance_to_exe in self.cached_values:
            client_id, value = self.cached_values.pop(self.instance_to_exe)
            self.executed_values[self.instance_to_exe] = value
            if value is not None:
                self.state, output = self.transitions(self.state)
            self.instance_to_exe += 1

    def leadership_acquired(self):
        running_instances_new = {}
        for instance, value in self.running_instances:
            self.refusals[instance] = 0
            self.get_proposer(instance).prepare()
            self.current_instance += 1
            running_instances_new[self.current_instance] = value
        self.running_instances = running_instances_new
        for instance, value in self.running_instances:
            self.refusals[instance] = 0
            self.get_proposer(instance).prepare(value)