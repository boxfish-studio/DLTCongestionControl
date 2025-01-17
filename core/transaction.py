from .global_params import *
from copy import copy

class Transaction:
    """
    Object to simulate a transaction and its edges in the DAG
    """
    def __init__(self, IssueTime, Parents, Node, Network, Work=0, Index=None, VisibleTime=None):
        self.IssueTime = IssueTime
        self.VisibleTime = VisibleTime
        self.Children = []
        self.Parents = Parents
        self.Network = Network
        self.Index = Network.TranIndex
        Network.InformedNodes[self.Index] = 0
        Network.ConfirmedNodes[self.Index] = 0
        self.Work = Work
        self.AWeight = Work
        self.LastAWUpdate = self
        if Node:
            self.Solid = False
            self.NodeID = Node.NodeID # signature of issuing node
            self.Eligible = False
            self.Confirmed = False
            self.EligibleTime = None
            Network.TranIssuer[Network.TranIndex] = Node.NodeID
        else: # genesis
            self.Solid = True
            self.NodeID = 0 # Genesis is issued by Node 0
            self.Eligible = True
            self.Confirmed = True
            self.EligibleTime = 0
        Network.TranIndex += 1

    def mark_confirmed(self, Node):
        self.Confirmed = True
        self.Network.ConfirmedNodes[self.Index] +=1

    def mark_eligible(self, Node):
        # mark this transaction as eligible and modify the tipset accordingly
        self.Eligible = True
        # add this to tipset if no eligible children
        isTip = True
        for c in self.Children:
            Node.Inbox.update_ready(c)
            if c.Eligible:
                isTip = False
                break
        if isTip:
            Node.TipsSet.append(self)
            Node.NodeTipsSet[self.NodeID].append(self)
        
        # remove parents from tip set
        for p in self.Parents:
            if p in Node.TipsSet:
                Node.TipsSet.remove(p)
                Node.NodeTipsSet[p.NodeID].remove(p)
            else:
                continue
    
    def updateAW(self, Node, updateTran=None, Work=None):
        if updateTran is None:
            assert Work is None
            updateTran = self
            Work = self.Work
        else:
            assert Work is not None
            self.AWeight += Work
            if self.AWeight >= CONF_WEIGHT:
                self.mark_confirmed(Node)

        self.LastAWUpdate = updateTran
        for p in self.Parents:
            if not p.Confirmed and p.LastAWUpdate != updateTran:
                p.updateAW(Node, updateTran, Work)
    
    def copy(self, Node):
        Tran = copy(self)
        parentIDs = [p.Index for p in Tran.Parents]
        parents = []
        for pID in parentIDs:
            # if we have the parents in the ledger already, include them as parents
            if pID in Node.Ledger:
                parents.append(Node.Ledger[pID])
        Tran.Parents = parents
        childrenIDs = [c.Index for c in Tran.Children]
        children = []
        for cID in childrenIDs:
            # if children are in our ledger already, then include them (needed for solidification)
            if cID in Node.Ledger:
                children.append(Node.Ledger[cID])
        Tran.Children = children
        if self.Index == 0:
            Tran.Eligible = True
            Tran.EligibleTime = 0
            Tran.Confirmed = True
            Tran.Solid = True
        else:
            Tran.Eligible = False
            Tran.EligibleTime = None
            Tran.Confirmed = False
            Tran.Solid = False
        return Tran

    def solidify(self, Node = None):
        if len(self.Parents)>2:
            print("more than 2 parents...")
        solidParents = [p for p in self.Parents if p.Solid]
        if len(solidParents)==1:
            if self.Parents[0].Index==0: # if parent is genesis
                self.Solid = True
        if len(solidParents)==2: # if two solid parents
            self.Solid = True
        if self.Solid:
            # if we already have some children of this solid transaction, they will possibly need to be solidified too.
            for c in self.Children:
                assert isinstance(c, Transaction)
                if self not in c.Parents:
                    if len(c.Parents)==2:
                        print("3rd parent being added...")
                    c.Parents.append(self)
                c.solidify()


    def is_ready(self):
        eligConfParents = [p for p in self.Parents if p.Eligible or p.Confirmed]
        if len(eligConfParents)==1:
            if self.Parents[0].Index==0: # if one parent eligible/confirmed
                return True
        if len(eligConfParents)==2: # if two parents eligible/confirmed
            return True
        return False

class SolRequest:
    '''
    Object to request solidification of a transaction
    '''
    def __init__(self, TranID):
        self.TranID = TranID

class PruneRequest:
    """
    Request to prune issued by node "NodeID"
    """
    def __init__(self, NodeID, Forward=False):
        self.NodeID = NodeID
        self.Forward = Forward # flag to forward messages from this node or not
