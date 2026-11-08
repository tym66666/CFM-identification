import argparse
import json
from pathlib import Path
from . import validate

parser = argparse.ArgumentParser(description='Offline benchmark integrity and reference replay. No API calls.')
parser.add_argument('--replay-references', action='store_true')
parser.add_argument('--output', type=Path)
args = parser.parse_args()
result = validate(replay_references=args.replay_references)
text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
if args.output:
    args.output.write_text(text, encoding='utf8')
print(text, end='')
