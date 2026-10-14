#!/usr/bin/env python3
"""Submit supplied Data safety CSV through applications.dataSafety. Offline by default."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

try:
    from .play_api import ADCTransport, API_ROOT, APIError, PlayError
    from .play_release import receipt, require
except ImportError:
    from play_api import ADCTransport, API_ROOT, APIError, PlayError
    from play_release import receipt, require

HEADERS = ('Question ID (machine readable)', 'Response ID (machine readable)', 'Response value', 'Answer requirement', 'Human-friendly question label')
REQUIREMENTS = {'OPTIONAL', 'REQUIRED', 'MULTIPLE_CHOICE', 'SINGLE_CHOICE', 'MAYBE_REQUIRED'}


def read_csv(path):
    data = Path(path).read_bytes()
    require(len(data) <= 4 * 1024 * 1024, 'Data safety CSV exceeds the local 4 MiB limit')
    text = data.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames) and set(HEADERS) <= set(reader.fieldnames), 'Use current Console export CSV headers: ' + ', '.join(HEADERS))
    rows = list(reader)
    require(bool(rows), 'Data safety CSV must include responses')
    seen, choices = set(), {}
    for index, row in enumerate(rows, 2):
        require(None not in row and all(value is not None for value in row.values()), f'CSV row {index} has wrong column count')
        question, response = row[HEADERS[0]], row[HEADERS[1]]
        require(bool(question.strip()) and (question, response) not in seen, f'CSV row {index}: missing question or duplicate response')
        seen.add((question, response))
        value, requirement = row['Response value'], row['Answer requirement']
        require(value in {'', 'TRUE', 'FALSE'} and requirement in REQUIREMENTS, f'CSV row {index}: use TRUE/FALSE/blank and known Answer requirement')
        require(requirement != 'REQUIRED' or value in {'TRUE','FALSE'}, f'CSV row {index}: REQUIRED response is blank')
        if requirement == 'SINGLE_CHOICE' and value == 'TRUE':
            choices[question] = choices.get(question, 0) + 1
            require(choices[question] <= 1, f'{question}: multiple TRUE answers for SINGLE_CHOICE')
    return {'file': str(Path(path).resolve()), 'text': text, 'bytes': data, 'sha256': hashlib.sha256(data).hexdigest(), 'rows': len(rows),
            'warnings': ['Syntax validation does not resolve conditional questions or prove data flows/SDK declarations. Use current Console template and evidence-backed responses.']}


def plan(package, csv_path, before_csv=None):
    require(isinstance(package, str) and bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+', package)), 'Invalid Android package')
    proposed = read_csv(csv_path)
    previous = read_csv(before_csv) if before_csv else None
    return {'status': 'offline-plan', 'package_name': package, 'proposed': {k:v for k,v in proposed.items() if k not in {'text','bytes'}},
            'before': {k:v for k,v in previous.items() if k not in {'text','bytes'}} if previous else None,
            'same_file_contents': proposed['sha256'] == previous['sha256'] if previous else None,
            'endpoint': f'{API_ROOT}/applications/{package}/dataSafety', 'payload_field': 'safetyLabels',
            'note': 'No edit or validateOnly/read declaration endpoint. Before live, provide a fresh prior CSV exported from Console; a successful write is not policy approval.'}


def apply(package, csv_path, before_csv, backup_directory, transport):
    summary = plan(package, csv_path, before_csv)
    require(before_csv is not None, 'Live Data safety requires --before-csv: Publisher exposes no declaration read/backup endpoint')
    proposed, previous = read_csv(csv_path), read_csv(before_csv)
    if summary['same_file_contents']:
        return dict(summary, status='unchanged', note='No write: proposed CSV matches supplied prior export')
    directory = Path(backup_directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory/'before.csv').write_bytes(previous['bytes'])
    (directory/'proposed.csv').write_bytes(proposed['bytes'])
    record = dict(status='submission-pending', package_name=package, before_sha256=previous['sha256'], proposed_sha256=proposed['sha256'], backup=str(directory.resolve()))
    receipt(directory/'transaction.json', record)
    try:
        response = transport.request('POST', summary['endpoint'], payload={'safetyLabels': proposed['text']})
        if response != {}:
            raise PlayError('Data safety response was not empty; write outcome unknown')
    except PlayError as exc:
        uncertain = not isinstance(exc, APIError) or exc.status == 408 or exc.status >= 500
        state = dict(record, status='submission-outcome-unknown' if uncertain else 'submission-rejected')
        try:
            receipt(directory/'transaction.json', state)
        except OSError:
            raise PlayError(f'{exc}; receipt update failed, inspect Console before retrying') from exc
        if uncertain:
            raise PlayError('Data safety write outcome is unknown; inspect Console before retrying. No automatic retry.') from exc
        raise
    result = dict(record, status='submitted', note='API accepted the CSV; confirm declarations/review and public labels in Console')
    try:
        receipt(directory/'transaction.json', result)
    except OSError:
        result['receipt_error'] = 'API accepted write but receipt save failed; do not repeat the write automatically'
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan','apply'))
    parser.add_argument('--package',required=True)
    parser.add_argument('--csv',required=True)
    parser.add_argument('--before-csv')
    parser.add_argument('--backup-directory')
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args(argv)
    try:
        summary=plan(args.package,args.csv,args.before_csv)
        if args.command=='plan' or not args.live:
            result=summary
        else:
            require(args.before_csv is not None and args.backup_directory is not None, 'Live Data safety requires --before-csv and a new --backup-directory')
            result=apply(args.package,args.csv,args.before_csv,args.backup_directory,ADCTransport())
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError,UnicodeError,csv.Error) as exc:
        print(str(exc),file=sys.stderr)
        return 2
    except PlayError as exc:
        print(str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
