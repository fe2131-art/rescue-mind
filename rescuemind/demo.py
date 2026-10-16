"""Run the grid prototype and optionally render its trace."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path
from .intent import IntentClassifier
from .sim import simulate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--instruction', default='避難所Bでは飲料水が不足しています。水を優先して届けてください')
    parser.add_argument('--mode', choices=['adaptive', 'fixed'], default='adaptive')
    parser.add_argument('--classifier', choices=['tfidf', 'keyword', 'minilm'], default='tfidf')
    parser.add_argument('--output', default='outputs/run.json')
    parser.add_argument('--render', action='store_true', help='create a PNG and an MP4 offline preview')
    args = parser.parse_args()
    r = simulate(args.instruction, args.mode, IntentClassifier(args.classifier))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(r), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in asdict(r).items() if k != 'history'}, ensure_ascii=False, indent=2))
    print('event trace:', str(out))
    if args.render:
        from .visualize import render
        render(r, out.parent)

if __name__ == '__main__':
    main()
