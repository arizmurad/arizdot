"""Cloud observations are historical evidence, never local worker telemetry."""
import json
import re
import time
from datetime import datetime,timezone
from pathlib import Path


def cloud_snapshot(path,material='Crystal'):
    path=Path(path)
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    observed=data.get('observed_UTC')
    if not isinstance(observed,str):raise ValueError('Cloud observation has no timestamp')
    stamp=datetime.fromisoformat(observed.replace('Z','+00:00'))
    if stamp.tzinfo is None:raise ValueError('Cloud timestamp must include a timezone')
    age=max(0,time.time()-stamp.timestamp())
    case=data.get('case','')
    w=re.search(r'_w(\d+)_r(\d+)',case)
    current='Colab'+(f' · {w[1]}/{w[2]} Ry' if w else '')
    iteration=data.get('iteration')
    accuracy=data.get('last_scf_error_Ry')
    target=data.get('target_Ry')
    metrics=f'SCF {iteration}' if isinstance(iteration,int) else 'İterasiya məlum deyil'
    if isinstance(accuracy,(int,float)):metrics+=f' · ΔE < {accuracy:.2e} Ry'
    if isinstance(target,(int,float)):metrics+=f' → {target:.0e} Ry'
    minutes=int(age//60)
    health=f'Son müşahidə: {minutes} dəqiqə əvvəl · Colab canlı bağlantısı yoxdur'
    return dict(title=material+' · Colab',current=current,metrics=metrics,health=health,
        next='Sonra: Colab statusunu yenilə',percent=None,active=False,status='Colab: son müşahidə',
        scope='Faiz ölçülmür · uzaq hesabın son qeydi',badge='OBSERVED',tone='amber',
        source=str(path),case=case,phase='cloud_observed',snapshot_status='stale' if age>120 else 'recorded',
        observation=True,observed_UTC=observed,output_age_seconds=age,controller_updated_seconds=age,
        iteration=iteration,accuracy_Ry=accuracy,target_Ry=target,process={},remote_pid=data.get('qe_pid'))
