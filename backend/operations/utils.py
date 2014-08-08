# TODO: this is a big mess!
# USE A consistent api!

import json

from .models import Operation, Workflow
from orchestra_core import op_register, wf_register
from orchestra_core.utils import get_async_result, reset_async_result, generate_uuid, revoke_if_running, get_async_state, resolve_partial
from rest_framework.exceptions import APIException
from celery.result import AsyncResult
from celery.task.control import revoke
import datetime






class ConnectedWorkflow(object):

    def __init__(self, name=None, oid=None, create_function=None):
        self.name = name
        self.oid = oid or generate_uuid()
        
        self.ops = []
        self.ops_ids = {}
        self.ops_names = {}
        self.ops_keys = {}

        if create_function:
            create_function(self)

    def get_operation(self, name):
        #op_fun = op_register.get_function(name)
        op = Operation(name=name, oid=generate_uuid())
        op.partials = {}
        return op

    def add_operation(self, op):
        self.ops.append(op)
        #TODO: check assigned ids
        self.ops_ids[op.oid] = True
        if op.name not in self.ops_names:

            self.ops_names[op.name] = 0;
        self.ops_names[op.name] += 1;

        self.ops_keys[op.oid] = op.name + "_" + str(self.ops_names[op.name])


    def connect(self, op1, op2, connector):
        connector(op1,op2)


    def save(self, **model_kwargs):
        """
        save all operations and the workflow
        """
        try:
            workflow = Workflow.objects.get(oid=self.oid)
        except Workflow.DoesNotExist:
            workflow = Workflow(name=self.name, oid=self.oid, **model_kwargs)
            workflow.save()

        for op in self.ops:
            op.workflow = workflow
            op.owner = workflow.owner
            op.save()

        return workflow

    def get_runnable_ops(self, data={}, rerun=[]):
        out = []
        missing = {}
        for op in self.ops:
            #filtering run operations
            
            if op.task and op.oid not in rerun:
                continue

            if op.oid in data:
                op_data = data[op.oid]
            else:
                op_data = {}
            x = missing_args(op, op_data)
            
            if not x:
                out.append(op)
            else:
                missing[op.oid] = x

        return out, missing


    def get_meta(self):
        out = {}
        out['name'] = self.name
        out['ops'] = []

        for op in self.ops:
            op_key = self.ops_keys[op.oid]
            partials = op.partials or {}
            out_partials = {}
            for k in partials:
                p = partials[k]
                if type(p) == dict and 'backend' in p:
                    op_name = self.ops_keys[p['id']]
                    out_partials[k] = { "source" : op_name }
                else:
                    out_partials[k] = partials[k]

            meta = op_register.meta[op.name]
            op_data = {"name" : op.name, "key": op_key, "meta" : meta, "partials" : out_partials }
            out['ops'].append(op_data)


        return out




    def load(self):
        wf = Workflow.objects.get(oid=self.oid)
        self.ops = wf.operations.all()
        self.name = wf.name
        return wf


def get_workflow_meta(name):
    wf_fun = wf_register.get_function(name)
    w = ConnectedWorkflow(name=name, create_function=wf_fun)
    return w.get_meta()
    


def create_workflow(name, **model_kwargs):
    """
    get workflow from register and created associated operations
    chaining them via partial args
    """

    wf_fun = wf_register.get_function(name)
    w = ConnectedWorkflow(name=name, create_function=wf_fun)
    out = w.save(**model_kwargs)
    return out



def load_workflow(wf_id):
    """
   
    """
    w = ConnectedWorkflow(oid=wf_id)
    w.load()
    return w


