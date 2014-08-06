import json

from .models import Operation, Workflow
from orchestra_core import op_register, wf_register
from orchestra_core.utils import get_async_result, reset_async_result, generate_uuid, revoke_if_running
from rest_framework.exceptions import APIException



def resolve_partial(partial):
    if type(partial) == dict:

        if 'backend' not in partial:
            raise ValueError('Backend not specified in partial')
        if partial['backend'] == 'celery':
            return get_async_result(partial['id'])
            
    return partial


def get_args_for_op(meta, data, partials):
    args = []
    args_not_found = []
    for arg in meta['args']:
        if arg not in data:
            
            if arg in partials:
                p = partials[arg]
                
                try:
                    res = resolve_partial(partials[arg])
                    args.append(res)
                except:
                    args_not_found.append(arg)

            else:
                args_not_found.append(arg)

        else:
            args.append(data[arg])

    return args, args_not_found


def missing_args(op, data={}):
    meta = op_register.meta[op.name]
    partials = op.partials or {}
    args, args_not_found = get_args_for_op(meta, data, partials)

    return args_not_found



def run_operation(op, data):
    """
    runs an operation (stored in db)
    """
    #let's check arguments
    meta = op_register.meta[op.name]
    args = []
    args_not_found = []
    
    partials = op.partials or {}

    if(op.task):
        revoke_if_running(op.task)
        reset_async_result(op.task)

    args, args_not_found = get_args_for_op(meta, data, partials)
    

    if args_not_found:
        raise APIException("Missing arguments, %s" % ','.join(args_not_found))    

    task = op_register.reg[op.name]
    run_args = {'args' : args}
    
    res = task.apply_async(args, task_id = op.assigned_id)
    task_id = res.task_id
    op.task = task_id
    op.args = json.dumps(run_args)
    op.save()

    return op


class ConnectedWorkflow(object):

    def __init__(self, name=None, assigned_id=None, create_function=None):
        self.name = name
        self.assigned_id = assigned_id or generate_uuid()
        
        self.ops = []
        self.ops_ids = {}
        self.ops_names = {}
        self.ops_keys = {}

        if create_function:
            create_function(self)

    def get_operation(self, name):
        #op_fun = op_register.get_function(name)
        op = Operation(name=name, assigned_id=generate_uuid())
        op.partials = {}
        return op

    def add_operation(self, op):
        self.ops.append(op)
        #TODO: check assigned ids
        self.ops_ids[op.assigned_id] = True
        if op.name not in self.ops_names:

            self.ops_names[op.name] = 0;
        self.ops_names[op.name] += 1;

        self.ops_keys[op.assigned_id] = op.name + "_" + str(self.ops_names[op.name])


    def connect(self, op1, op2, connector):
        connector(op1,op2)


    def save(self, **model_kwargs):
        """
        save all operations and the workflow
        """
        try:
            workflow = Workflow.objects.get(assigned_id=self.assigned_id)
        except Workflow.DoesNotExist:
            workflow = Workflow(name=self.name, assigned_id=self.assigned_id, **model_kwargs)
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
            
            if op.task and op.assigned_id not in rerun:
                continue

            if op.assigned_id in data:
                op_data = data[op.assigned_id]
            else:
                op_data = {}
            x = missing_args(op, op_data)
            
            if not x:
                out.append(op)
            else:
                missing[op.assigned_id] = x

        return out, missing


    def get_meta(self):
        out = {}
        out['name'] = self.name
        out['ops'] = []

        print "o", self.ops_names

        for op in self.ops:
            op_key = self.ops_keys[op.assigned_id]
            partials = op.partials or {}
            out_partials = {}
            for k in partials:
                p = partials[k]
                if 'backend' in p:
                    op_name = self.ops_keys[p['id']]
                    out_partials[k] = "from:"+op_name
                else:
                    out_partials[k] = partials[k]

            meta = op_register.meta[op.name]
            op_data = {"name" : op.name, "key": op_key, "meta" : meta, "partials" : out_partials }
            out['ops'].append(op_data)


        return out




    def load(self):
        wf = Workflow.objects.get(assigned_id=self.assigned_id)
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
    w = ConnectedWorkflow(assigned_id=wf_id)
    w.load()
    return w



def run_workflow(wf_id, data={}, rerun=[]):
    w = ConnectedWorkflow(assigned_id=wf_id)
    wf = w.load()
    rops, missing = w.get_runnable_ops(data, rerun=rerun)
    xops = [x.assigned_id for x in w.ops if x.task and x.assigned_id not in rerun]
    run_ops = []
    if rops:
        for r in rops:
            op_data = data.get(r.assigned_id,{})
            run_operation(r, op_data)
            run_ops.append(r.assigned_id)

    return {"just_run" : run_ops, "missing_args" : missing, "previously_run" : xops}





    
