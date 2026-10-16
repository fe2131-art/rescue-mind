"""Evaluate fixed vs adaptive grid planning and tiny held-out intent dataset."""
import argparse
import csv
import json
from pathlib import Path
from .intent import IntentClassifier, HELD_OUT
from .sim import simulate


def evaluation(classifiers=('tfidf', 'keyword'), out_dir='outputs'):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for name in classifiers:
        model = IntentClassifier(name)
        for instruction, truth in HELD_OUT:
            prediction = model.classify(instruction)
            for mode in ('fixed', 'adaptive'):
                run = simulate(instruction + ' 避難所B', mode, model)
                records.append({
                    'classifier': name, 'mode': mode, 'instruction': instruction,
                    'truth': truth, 'prediction': prediction.item,
                    'correct': int(prediction.item == truth),
                    'success': int(run.success and prediction.item == truth),
                    'route_completed': int(run.success),
                    'steps': run.path_length, 'replans': run.replans,
                    'reason': run.reason,
                })
    with (out/'trials.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary=[]
    for name in classifiers:
        for mode in ('fixed', 'adaptive'):
            rs=[r for r in records if r['classifier']==name and r['mode']==mode]
            summary.append({
                'classifier': name, 'mode': mode, 'n': len(rs),
                'intent_accuracy': round(sum(r['correct'] for r in rs)/len(rs), 3),
                'task_success_rate': round(sum(r['success'] for r in rs)/len(rs), 3),
                'navigation_completion_rate': round(sum(r['route_completed'] for r in rs)/len(rs), 3),
                'mean_steps': round(sum(r['steps'] for r in rs)/len(rs), 2),
                'mean_replans': round(sum(r['replans'] for r in rs)/len(rs), 2),
            })
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output-dir', default='outputs')
    p.add_argument('--include-minilm', action='store_true')
    a=p.parse_args()
    classifiers=['tfidf', 'keyword'] + (['minilm'] if a.include_minilm else [])
    print(json.dumps(evaluation(classifiers, a.output_dir), ensure_ascii=False, indent=2))

if __name__=='__main__':
    main()
