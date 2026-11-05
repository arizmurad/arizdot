"""Small producer helper for any Python background worker; standard JSON output."""
from pathlib import Path
import time
from activation import write_json


class JobSignal:
    def __init__(self,path,run_id):
        if not isinstance(run_id,str) or not run_id:raise ValueError('Use the actual run identity')
        self.path=Path(path);self.run_id=run_id

    def write(self,state,current,steps=None,completed=None,total=None,next_step='',metrics=''):
        value=dict(run_id=self.run_id,updated_at=time.time(),state=state,current=current,next=next_step,metrics=metrics)
        if steps is not None:value['steps']=steps
        if completed is not None:value['completed']=completed
        if total is not None:value['total']=total
        from background_jobs import normalize
        if not normalize(value,dict(run_id=self.run_id)):raise ValueError('Invalid job status')
        write_json(self.path,value)
        return value
