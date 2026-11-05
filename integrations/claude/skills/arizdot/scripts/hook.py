import runpy
import sys
from bridge import app_root


if __name__=='__main__':
    try:
        root=app_root();sys.path.insert(0,str(root))
        runpy.run_path(str(root/'claude_hook.py'),run_name='__main__')
    except (OSError,ValueError,KeyError) as error:
        print('arizdot hook unavailable: '+type(error).__name__,file=sys.stderr)
