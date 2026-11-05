"""Private subprocess: only Kaggle get/status/log methods, never launch or stop."""
import contextlib
import io
import json
import sys
import threading
import time
from kaggle_remote import MarkerReader,validate,timestamp


def run(binding):
    kernel=validate(binding);output=sys.stdout;lock=threading.Lock()
    def emit(**fields):
        with lock:
            output.write(json.dumps(fields)+'\n');output.flush()
    try:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            from kaggle.api.kaggle_api_extended import KaggleApi
            api=KaggleApi();api.authenticate()
        if len(kernel.split('/'))==2:
            from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
            with api.build_kaggle_client() as client:
                request=ApiGetKernelRequest();request.user_name,request.kernel_slug=kernel.split('/')
                metadata=client.kernels.kernels_api_client.get_kernel(request).metadata
                # Resolve once, then pin vN. A scriptVersionId is not a vN label.
                if metadata is None or metadata.current_version_number<=0:raise ValueError('No version')
                # Metadata last_run_time can lag a currently running version.
                # Pin the returned vN and validate telemetry against expected
                # case identities instead of rejecting a run on that timestamp.
                kernel+='/'+str(metadata.current_version_number)
        emit(resolved_ref=kernel)
    except (Exception,SystemExit):emit(connection='api_error');return
    def stream():
        parser=MarkerReader(binding)
        while True:
            try:
                for event in api.kernels_logs_stream(kernel):
                    for data in parser.feed(event.get('data','')):
                        emit(telemetry=data,received_at=time.time())
                time.sleep(15)
            except (Exception,SystemExit):
                emit(log_connection='unavailable');time.sleep(15)
    stream_thread=threading.Thread(target=stream,daemon=True);stream_thread.start()
    while True:
        try:
            response=api.kernels_status(kernel)
            emit(connection='connected',platform_status=response.status.name,checked_at=time.time())
            if response.status.name in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED'):
                stream_thread.join(timeout=5);return
        except (Exception,SystemExit):emit(connection='api_error')
        time.sleep(15)


if __name__=='__main__':
    try:run(json.load(sys.stdin))
    except (Exception,SystemExit):pass
