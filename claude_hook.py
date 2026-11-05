"""Observer only: no hook decisions, no stdout, no automatic UI launch."""
import json
import sys
from claude_support import record_hook


def main():
    try:
        raw=sys.stdin.buffer.read(1_048_577)
        if len(raw)>1_048_576:raise ValueError('Hook input too large')
        record_hook(json.loads(raw.decode('utf-8-sig')))
    except (OSError,ValueError,TypeError,KeyError,TimeoutError) as error:
        print('arizdot observer skipped: '+type(error).__name__,file=sys.stderr)
    return 0


if __name__=='__main__':raise SystemExit(main())
