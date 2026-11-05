"""Evidence-based freshness; a quiet log alone is not a dead process."""
def classify(job,cpu_rate=None):
    if not job:return 'offline'
    phase=job.get('phase')
    if phase in ('completed','stopped_by_user','needs_review'):return 'recorded'
    if job.get('badge')=='STOP' or job.get('source_error'):return 'offline'
    if phase in ('waiting_memory','waiting_for_upstream'):
        return 'stale' if job.get('controller_updated_seconds',999)>90 else 'live'
    if phase=='computing':
        if job.get('badge')=='CHECK':return 'live'
        age=job.get('output_age_seconds')
        if cpu_rate is not None and cpu_rate>.01:return 'live'
        if age is not None and age<=120:return 'live'
        return 'stale'
    return 'stale'
