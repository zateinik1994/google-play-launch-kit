#!/usr/bin/env python3
"""Transactional Publisher assets, AAB and track delivery. Offline unless --live."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import secrets
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

try:
    from .play_api import ADCTransport, API_ROOT, PlayError, APIError, PlayPublisher, listing_map, desired_listing, plan_listings, write_json
    from .image_validation import inspect_image, validate_image
except ImportError:
    from play_api import ADCTransport, API_ROOT, PlayError, APIError, PlayPublisher, listing_map, desired_listing, plan_listings, write_json
    from image_validation import inspect_image, validate_image

IMAGE_TYPES = {'icon', 'featureGraphic', 'phoneScreenshots', 'sevenInchScreenshots', 'tenInchScreenshots', 'tvScreenshots', 'tvBanner', 'wearScreenshots'}
DETAIL_FIELDS = {'defaultLanguage', 'contactEmail', 'contactPhone', 'contactWebsite'}
RELEASE_FIELDS = {'name', 'versionCodes', 'status', 'userFraction', 'releaseNotes', 'inAppUpdatePriority', 'countryTargeting'}
LOCALE = re.compile(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*')


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(data)
    return value.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def locale(value):
    require(isinstance(value, str) and bool(LOCALE.fullmatch(value)), 'Expected a BCP-47 language tag; Console confirms language support')


def file_info(value, directory, *, image_type=None, bundle=False):
    require(isinstance(value, str) and bool(value.strip()), 'File path must be non-empty')
    path = (Path(directory) / value).resolve()
    require(path.is_file(), f'File does not exist: {path}')
    if bundle:
        require(path.suffix.lower() == '.aab' and 0 < path.stat().st_size <= 2 * 1024**3, 'Bundle must be a non-empty AAB within the local 2 GiB limit')
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                require({'BundleConfig.pb', 'base/manifest/AndroidManifest.xml'} <= names, 'AAB needs BundleConfig.pb and base manifest')
        except zipfile.BadZipFile as exc:
            raise ValueError('AAB is not a valid ZIP container') from exc
        mime = 'application/octet-stream'
    else:
        kind = {'icon': 'icon', 'featureGraphic': 'feature-graphic', 'phoneScreenshots': 'screenshot',
                'sevenInchScreenshots': 'tablet-screenshot', 'tenInchScreenshots': 'tablet-screenshot'}.get(image_type)
        if kind:
            info = validate_image(path, kind)
            require(info['valid'], f'{path}: ' + '; '.join(info['errors']))
        else:
            info = inspect_image(path)
            require(info['format'] in {'PNG', 'JPEG'}, 'Expected PNG/JPEG')
        mime = 'image/png' if info['format'] == 'PNG' else 'image/jpeg'
    return {'file': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size, 'mime': mime}


def validate_config(config, directory='.'):
    require(isinstance(config, dict), 'Release config must be an object')
    require(not set(config) - {'package_name', 'listings', 'delete_listings', 'details', 'images', 'bundle', 'tracks', 'changes_not_sent_for_review'}, 'Unknown release config fields')
    package = config.get('package_name')
    require(isinstance(package, str) and bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+', package)), 'Expected Android package_name')
    require(any(config.get(key) for key in ('listings', 'delete_listings', 'details', 'images', 'bundle', 'tracks')), 'Specify a non-empty operation')
    result = copy.deepcopy(config)
    if 'listings' in config:
        plan_listings(config['listings'])
    if 'delete_listings' in config:
        require(isinstance(config['delete_listings'], list) and bool(config['delete_listings']), 'delete_listings must be a non-empty locale array')
        for language in config['delete_listings']:
            locale(language)
        require(len(set(config['delete_listings'])) == len(config['delete_listings']) and not set(config['delete_listings']) & set(config.get('listings', {})), 'Do not update/delete the same locale or repeat deletions')
    if 'details' in config:
        details = config['details']
        require(isinstance(details, dict) and bool(details) and not set(details) - DETAIL_FIELDS and all(isinstance(v, str) for v in details.values()), 'details supports defaultLanguage/contactEmail/contactPhone/contactWebsite only')
        if 'defaultLanguage' in details:
            locale(details['defaultLanguage'])
        if details.get('contactWebsite'):
            require(details['contactWebsite'].startswith('https://'), 'contactWebsite must be HTTPS')
        if details.get('contactEmail'):
            require(bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', details['contactEmail'])), 'Invalid contactEmail')
    require(isinstance(config.get('changes_not_sent_for_review', False), bool), 'changes_not_sent_for_review must be boolean')
    if 'bundle' in config:
        bundle = config['bundle']
        require(isinstance(bundle, dict) and not set(bundle) - {'file', 'expected_version_code'}, 'bundle supports file/expected_version_code')
        result['bundle'] = dict(bundle, **file_info(bundle.get('file'), directory, bundle=True))
        if 'expected_version_code' in bundle:
            require(type(bundle['expected_version_code']) is int and 1 <= bundle['expected_version_code'] <= 2100000000, 'Invalid expected_version_code')
    images = config.get('images', [])
    require(isinstance(images, list), 'images must be a list')
    seen = set()
    for index, item in enumerate(images):
        require(isinstance(item, dict) and not set(item) - {'language', 'image_type', 'operation', 'files', 'ids', 'all'}, 'Unknown image operation fields')
        locale(item.get('language'))
        require(isinstance(item.get('image_type'), str) and item['image_type'] in IMAGE_TYPES, 'Unsupported AppImageType')
        key = (item['language'], item['image_type'])
        require(item['language'] not in config.get('delete_listings', []), 'Cannot edit images of a deleted locale')
        require(key not in seen, 'Use one operation per image language/type')
        seen.add(key)
        operation = item.get('operation')
        require(isinstance(operation, str) and operation in {'append', 'replace', 'delete', 'reorder'}, 'Image operation must be append/replace/delete/reorder')
        if operation in {'append', 'replace'}:
            require(set(item) == {'language', 'image_type', 'operation', 'files'} and isinstance(item['files'], list) and bool(item['files']), 'append/replace requires non-empty ordered files only')
            maximum = 1 if item['image_type'] in {'icon', 'featureGraphic', 'tvBanner'} else 8
            require(len(item['files']) <= maximum, 'Too many image files for this type')
            result['images'][index]['files'] = [file_info(path, directory, image_type=item['image_type']) for path in item['files']]
        else:
            if operation == 'delete' and item.get('all') is True:
                require(set(item) == {'language', 'image_type', 'operation', 'all'}, 'delete all cannot include ids/files')
            else:
                require(set(item) == {'language', 'image_type', 'operation', 'ids'} and isinstance(item['ids'], list) and bool(item['ids']) and all(isinstance(i, str) and bool(i) for i in item['ids']) and len(set(item['ids'])) == len(item['ids']), 'delete/reorder requires unique non-empty ids')
    tracks = config.get('tracks', [])
    require(isinstance(tracks, list), 'tracks must be a list')
    seen_tracks = set()
    for track in tracks:
        require(isinstance(track, dict) and set(track) == {'track', 'releases'}, 'Track requires track/releases')
        name = track['track']
        require(isinstance(name, str) and bool(name) and not any(c.isspace() or c in '/?#' for c in name) and name not in seen_tracks, 'Use an exact unique API track identifier')
        seen_tracks.add(name)
        require(isinstance(track['releases'], list), 'releases must be an array (empty explicitly clears track)')
        for release in track['releases']:
            require(isinstance(release, dict) and not set(release) - RELEASE_FIELDS, 'Unsupported release fields')
            status = release.get('status')
            require(isinstance(status, str) and status in {'draft', 'inProgress', 'halted', 'completed'}, 'Specify explicit release status')
            codes = release.get('versionCodes')
            require(isinstance(codes, list) and bool(codes) and all(isinstance(code, str) and (code == '$uploaded' and 'bundle' in config or code.isascii() and code.isdigit() and 1 <= int(code) <= 2100000000) for code in codes) and len(set(codes)) == len(codes), 'versionCodes: unique positive strings, or $uploaded with bundle')
            expected = config.get('bundle', {}).get('expected_version_code')
            resolved_codes = [str(expected) if code == '$uploaded' and expected is not None else code if code == '$uploaded' else str(int(code)) for code in codes]
            require(len(set(resolved_codes)) == len(resolved_codes), 'versionCodes must be numerically unique, including expected uploaded version')
            if status == 'inProgress':
                require('userFraction' in release, 'inProgress requires explicit userFraction')
            if 'userFraction' in release:
                fraction = release['userFraction']
                require(status in {'inProgress', 'halted'} and type(fraction) in {int, float} and math.isfinite(fraction) and 0 < fraction < 1, 'userFraction must be 0..1 exclusive for inProgress/halted only')
            if 'name' in release:
                require(isinstance(release['name'], str), 'Release name must be text')
            if 'inAppUpdatePriority' in release:
                require(type(release['inAppUpdatePriority']) is int and 0 <= release['inAppUpdatePriority'] <= 5, 'inAppUpdatePriority must be 0..5')
            notes = release.get('releaseNotes', [])
            require(isinstance(notes, list), 'releaseNotes must be an array')
            languages = set()
            for note in notes:
                require(isinstance(note, dict) and set(note) == {'language', 'text'}, 'releaseNotes entries require language/text')
                locale(note['language'])
                require(note['language'] not in languages and isinstance(note['text'], str) and len(note['text']) <= 500, 'Release notes: unique language, text at most 500 Unicode code points')
                languages.add(note['language'])
            if 'countryTargeting' in release:
                target = release['countryTargeting']
                require(name == 'production' and status == 'inProgress' and isinstance(target, dict) and not set(target) - {'countries', 'includeRestOfWorld'}, 'countryTargeting requires production inProgress')
                require(isinstance(target.get('countries'), list) and all(isinstance(c, str) and bool(re.fullmatch('[A-Z]{2}', c)) for c in target['countries']), 'countries must be two-letter codes')
                require(isinstance(target.get('includeRestOfWorld', False), bool), 'includeRestOfWorld must be boolean')
    return result


def plan(config, directory='.', current=None):
    prepared = validate_config(config, directory)
    changes = {}
    if current is not None:
        require(isinstance(current, dict) and current.get('package_name') == prepared['package_name'], 'Baseline package must match config')
        if config.get('listings'):
            changes['listings'] = plan_listings(config['listings'], current.get('listings', {}))
        changes['details'] = {key: {'from': current.get('details', {}).get(key), 'to': value} for key, value in config.get('details', {}).items()}
        by_track = {track['track']: track for track in current.get('tracks', [])}
        changes['tracks'] = [{'track': track['track'], 'from': by_track.get(track['track']), 'to': track} for track in config.get('tracks', [])]
    return {'status': 'offline-plan', 'baselineProvided': current is not None, 'package_name': prepared['package_name'],
            'operations': prepared, 'changes': changes, 'baseline': current, 'note': 'No network calls. tracks.releases replaces desired releases; include retained versions. $uploaded resolves from the upload response. Review/publishing settings apply after commit.'}


def receipt(path, data):
    """Atomic local lifecycle record; never includes signed upload session URLs."""
    target = Path(path)
    temporary = target.with_name(target.name + '-' + secrets.token_hex(4) + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def check_files(prepared):
    files = [f for group in prepared.get('images', []) for f in group.get('files', [])]
    if prepared.get('bundle'):
        files.append(prepared['bundle'])
    for info in files:
        require(digest(info['file']) == info['sha256'], f"File changed after planning: {info['file']}")


class ReleasePublisher(PlayPublisher):
    def image_url(self, edit_id, language, image_type):
        return f'{self._edit_url(edit_id)}/listings/{quote(language, safe="")}/{image_type}'

    def snapshot_edit(self, edit_id, groups=None):
        base = self._edit_url(edit_id)
        listings = listing_map(self.transport.request('GET', base + '/listings'))
        details = self.transport.request('GET', base + '/details')
        tracks = self.transport.request('GET', base + '/tracks').get('tracks', [])
        bundles = self.transport.request('GET', base + '/bundles').get('bundles', [])
        if (not isinstance(details, dict) or any(not isinstance(v, str) for v in details.values())
                or not isinstance(tracks, list) or any(not isinstance(t, dict) or not isinstance(t.get('track'), str) or not t['track'] or not isinstance(t.get('releases', []), list) for t in tracks)
                or not isinstance(bundles, list) or any(not isinstance(b, dict) or type(b.get('versionCode')) is not int for b in bundles)):
            raise PlayError('Invalid Publisher snapshot')
        if len({t['track'] for t in tracks}) != len(tracks):
            raise PlayError('Duplicate track identifiers in Publisher snapshot')
        images = []
        if groups is None:
            groups = [{'language': language, 'image_type': kind} for language in listings for kind in sorted(IMAGE_TYPES)]
        for group in groups:
            if group['language'] not in listings:
                current = []  # New locale must be added before images.upload.
            else:
                current = self.transport.request('GET', self.image_url(edit_id, group['language'], group['image_type'])).get('images', [])
            if not isinstance(current, list) or any(not isinstance(i, dict) or not isinstance(i.get('id'), str) or not i['id'] for i in current):
                raise PlayError('Invalid images.list response')
            if len({i['id'] for i in current}) != len(current):
                raise PlayError('Duplicate images.list identifiers')
            images.append({'language': group['language'], 'image_type': group['image_type'], 'images': current})
        return {'package_name': self.package_name, 'listings': listings, 'details': details, 'tracks': tracks, 'bundles': bundles, 'images': images}

    def snapshot(self, groups=None):
        with self.new_edit() as edit:
            return self.snapshot_edit(edit.id, groups)

    def release_state(self, track):
        """Read review/publication summaries without creating an invalidating edit."""
        require(isinstance(track, str) and bool(track) and not any(c.isspace() or c in '/?#' for c in track), 'Use an exact API track identifier')
        endpoint = f'{API_ROOT}/applications/{quote(self.package_name, safe="")}/tracks/{quote(track, safe="")}/releases'
        response = self.transport.request('GET', endpoint)
        releases = response.get('releases', [])
        if not isinstance(releases, list) or len(releases) > 20:
            raise PlayError('Release state response has invalid releases; no state confirmed')
        summaries = []
        for release in releases:
            if not isinstance(release, dict) or release.get('track') != track:
                raise PlayError('Release state summary has an invalid or different track')
            name = release.get('releaseName', '')
            state = release.get('releaseLifecycleState', 'RELEASE_LIFECYCLE_STATE_UNSPECIFIED')
            artifacts = release.get('activeArtifacts', [])
            if not isinstance(name, str) or not isinstance(state, str) or not state or not isinstance(artifacts, list):
                raise PlayError('Release state summary has invalid fields')
            if any(not isinstance(artifact, dict) or type(artifact.get('versionCode')) is not int or not 1 <= artifact['versionCode'] <= 2100000000 for artifact in artifacts):
                raise PlayError('Release state summary has invalid active versionCodes')
            summaries.append(dict(release, releaseName=name, releaseLifecycleState=state, activeArtifacts=artifacts))
        return {'status': 'live-read', 'package_name': self.package_name, 'track': track, 'releases': summaries,
                'source': 'Android Publisher applications.tracks.releases.list', 'endpoint': endpoint,
                'retrieved_at_utc': datetime.now(timezone.utc).isoformat(), 'maximum_releases': 20,
                'note': 'No edit created. Excludes obsolete releases; not a full release history. PUBLISHED includes partial and halted releases, and does not prove store listing visibility for a market/locale.'}

    def backup(self, snapshot, directory, desired):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        write_json(directory/'snapshot.json', snapshot)
        rollback = {'package_name': self.package_name}
        affected_locales = set(desired.get('listings', {})) | set(desired.get('delete_listings', []))
        if affected_locales:
            # Do not invent old values for locales that did not previously exist.
            # An omitted optional video preserves its current value during apply.
            # Restore absence explicitly, so adding the first video is reversible.
            rollback['listings'] = {lang: dict(snapshot['listings'][lang], video=snapshot['listings'][lang].get('video', ''))
                                    for lang in affected_locales if lang in snapshot['listings']}
            if not rollback['listings']:
                del rollback['listings']
            added = set(desired.get('listings', {})) - set(snapshot['listings'])
            if added:
                rollback['delete_listings'] = sorted(added)
        if desired.get('details'):
            rollback['details'] = {key: snapshot['details'].get(key, '') for key in desired['details']}
        if desired.get('tracks'):
            names = {t['track'] for t in desired['tracks']}
            rollback['tracks'] = [{k: v for k, v in track.items() if k in {'track', 'releases'}} for track in snapshot['tracks'] if track.get('track') in names]
        saved_groups = []
        for position, group in enumerate(snapshot['images']):
            saved = []
            for number, resource in enumerate(group['images']):
                url = resource.get('url')
                if not isinstance(url, str) or not url:
                    raise PlayError('Image backup has no download URL; no changes applied')
                data = self.transport.download_bytes(url)
                algorithm = 'sha256' if resource.get('sha256') else 'sha1'
                expected = resource.get(algorithm)
                if not isinstance(expected, str) or not re.fullmatch('[0-9A-Fa-f]{64}' if algorithm == 'sha256' else '[0-9A-Fa-f]{40}', expected):
                    raise PlayError('Original image checksum is missing; cannot guarantee reversible image replacement')
                if hashlib.new(algorithm, data).hexdigest() != expected.lower():
                    # Image.url can serve a scaled preview. Read the original-size variant.
                    data = self.transport.download_bytes(url.split('=s')[0] + '=s0')
                if hashlib.new(algorithm, data).hexdigest() != expected.lower():
                    raise PlayError('Image backup checksum differs from original; no destructive changes applied')
                extension = '.png' if data.startswith(b'\x89PNG') else '.jpg'
                path = directory/f'image-{position}-{number}{extension}'
                with path.open('xb') as output:
                    output.write(data)
                inspect_image(path)
                saved.append(dict(resource, backup_file=str(path.resolve()), backup_sha256=digest(path)))
            saved_groups.append(dict(group, images=saved))
        snapshot['images'] = saved_groups
        write_json(directory/'assets.json', {'images': saved_groups})
        restore = []
        for group in saved_groups:
            if group['language'] in rollback.get('delete_listings', []):
                continue
            files = [image['backup_file'] for image in group['images']]
            restore.append({'language': group['language'], 'image_type': group['image_type'], 'operation': 'replace', 'files': files} if files else {'language': group['language'], 'image_type': group['image_type'], 'operation': 'delete', 'all': True})
        if restore:
            rollback['images'] = restore
        write_json(directory/'rollback.json', rollback)
        return directory

    def apply(self, config, *, directory='.', backup_directory, validate_only=False):
        token = secrets.token_hex(16)
        try:
            return self._apply(config, directory=directory, backup_directory=backup_directory,
                               validate_only=validate_only, operation_token=token)
        except Exception:
            # Preserve a known commit result/uncertainty; annotate only our own staging record.
            path = Path(backup_directory)/'transaction.json'
            try:
                state = json.loads(path.read_text())
                if state.get('operation_token') == token and state.get('status') == 'staging':
                    receipt(path, dict(state, status='staging-failed', cleanup='Edit deletion attempted; inspect any reported cleanup error'))
            except (OSError, ValueError):
                pass
            raise

    def _apply(self, config, *, directory, backup_directory, validate_only, operation_token):
        prepared = validate_config(config, directory)
        require(prepared['package_name'] == self.package_name, 'Config package_name differs from the Publisher client target; no API calls made')
        check_files(prepared)
        if os.path.lexists(backup_directory):
            raise FileExistsError('Backup directory already exists; choose a new path before creating an edit')
        with self.new_edit() as edit:
            base = self._edit_url(edit.id)
            groups = list(prepared.get('images', []))
            groups += [{'language': language, 'image_type': kind} for language in prepared.get('delete_listings', []) for kind in sorted(IMAGE_TYPES)]
            snapshot = self.snapshot_edit(edit.id, groups)
            current_groups = {(g['language'], g['image_type']): g['images'] for g in snapshot['images']}
            for group in prepared.get('images', []):
                current = current_groups[(group['language'], group['image_type'])]
                ids = [image['id'] for image in current]
                if group['operation'] == 'reorder':
                    require(set(group['ids']) == set(ids) and len(group['ids']) == len(ids), 'reorder must specify every current image ID exactly once')
                if group['operation'] == 'delete' and not group.get('all'):
                    require(set(group['ids']) <= set(ids), 'delete IDs are absent in current images')
                if group['operation'] == 'append':
                    maximum = 1 if group['image_type'] in {'icon', 'featureGraphic', 'tvBanner'} else 8
                    require(len(current) + len(group['files']) <= maximum, 'Append exceeds current image capacity; use replace')
                require(group['language'] in snapshot['listings'] or group['language'] in prepared.get('listings', {}), 'Images need an existing listing or listing text in the same config')
            available_tracks = {t.get('track') for t in snapshot['tracks']}
            require(all(t['track'] in available_tracks for t in prepared.get('tracks', [])), 'Track does not exist; use exact identifier from snapshot/Console')
            require(set(prepared.get('delete_listings', [])) <= set(snapshot['listings']), 'Deleted locales are absent in snapshot')
            backup = self.backup(snapshot, backup_directory, prepared)
            lifecycle = {'status': 'staging', 'editId': edit.id, 'package_name': self.package_name, 'backup': str(backup), 'operation_token': operation_token}
            receipt(backup/'transaction.json', lifecycle)
            # All backups must be complete before the first upload/PUT/DELETE.
            for change in plan_listings(prepared.get('listings', {}), snapshot['listings'])['changes'] if prepared.get('listings') else []:
                language = change['language']
                self.transport.request('PUT', base + '/listings/' + quote(language, safe=''), payload=desired_listing(language, prepared['listings'][language], snapshot['listings'].get(language)))
            for language in prepared.get('delete_listings', []):
                self.transport.request('DELETE', base + '/listings/' + quote(language, safe=''))
            if prepared.get('details'):
                self.transport.request('PATCH', base + '/details', payload=prepared['details'])
            for group, old in zip(prepared.get('images', []), snapshot['images']):
                url = self.image_url(edit.id, group['language'], group['image_type'])
                operation = group['operation']
                if operation in {'replace', 'reorder'} or operation == 'delete' and group.get('all'):
                    self.transport.request('DELETE', url)
                elif operation == 'delete':
                    for image_id in group['ids']:
                        self.transport.request('DELETE', url + '/' + quote(image_id, safe=''))
                files = group.get('files', [])
                if operation == 'reorder':
                    by_id = {resource['id']: resource for resource in old['images']}
                    files = [file_info(by_id[i]['backup_file'], '.', image_type=group['image_type']) for i in group['ids']]
                for info in files:
                    require(digest(info['file']) == info['sha256'], 'Image changed before upload')
                    response = self.transport.upload_media(url.replace(API_ROOT, API_ROOT.replace('/androidpublisher/', '/upload/androidpublisher/'), 1), info['file'], info['mime'])
                    if not isinstance(response.get('image'), dict) or not response['image'].get('id'):
                        raise PlayError('Upload returned no image ID; inspect edit before retrying')
            uploaded = None
            if prepared.get('bundle'):
                bundle = prepared['bundle']
                require(digest(bundle['file']) == bundle['sha256'], 'AAB changed before upload')
                response = self.transport.upload_media(base.replace(API_ROOT, API_ROOT.replace('/androidpublisher/', '/upload/androidpublisher/'), 1) + '/bundles', bundle['file'], bundle['mime'], resumable=True)
                uploaded = response.get('versionCode')
                if type(uploaded) is not int or not 1 <= uploaded <= 2100000000:
                    raise PlayError('Bundle response has no valid versionCode; outcome unknown')
                require(bundle.get('expected_version_code', uploaded) == uploaded, 'Uploaded versionCode differs from expected; edit discarded')
            tracks = copy.deepcopy(prepared.get('tracks', []))
            for track in tracks:
                for release in track['releases']:
                    release['versionCodes'] = [str(uploaded) if code == '$uploaded' else str(int(code)) for code in release['versionCodes']]
                    require(len(set(release['versionCodes'])) == len(release['versionCodes']), 'Uploaded versionCode duplicates a retained version; edit discarded')
                self.transport.request('PUT', base + '/tracks/' + quote(track['track'], safe=''), payload=track)
            self.transport.request('POST', base + ':validate')
            result = {'status': 'validated-only' if validate_only else 'committed', 'editId': edit.id, 'backup': str(backup), 'uploadedVersionCode': uploaded, 'tracks': tracks}
            if not validate_only:
                receipt(backup/'transaction.json', dict(lifecycle, status='commit-pending', uploadedVersionCode=uploaded, tracks=tracks))
                try:
                    self.commit_edit(edit, changes_not_sent_for_review=prepared.get('changes_not_sent_for_review', False))
                except PlayError as exc:
                    uncertain = not isinstance(exc, APIError) or exc.status == 408 or exc.status >= 500
                    try:
                        receipt(backup/'transaction.json', dict(lifecycle, status='commit-outcome-unknown' if uncertain else 'commit-rejected'))
                    except OSError:
                        raise PlayError(f'{exc}; transaction receipt could not be updated; inspect Console before retrying') from exc
                    raise
            try:
                receipt(backup/'transaction.json', result)
                write_json(backup/'result.json', result)
            except OSError:
                result['receipt_error'] = 'Confirmed result could not be persisted; use returned editId and inspect Console. Do not repeat commit.'
            return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('plan', 'validate', 'apply'):
        child = sub.add_parser(name)
        child.add_argument('--config', required=True)
        child.add_argument('--live', action='store_true')
        child.add_argument('--output')
        child.add_argument('--current')
        child.add_argument('--backup-directory')
    snapshot_parser = sub.add_parser('snapshot')
    snapshot_parser.add_argument('--package', required=True)
    snapshot_parser.add_argument('--language', action='append')
    snapshot_parser.add_argument('--image-type', action='append', choices=sorted(IMAGE_TYPES))
    snapshot_parser.add_argument('--live', action='store_true')
    snapshot_parser.add_argument('--output')
    state_parser = sub.add_parser('release-state', help='Read track review/publication state outside an edit; offline unless --live')
    state_parser.add_argument('--package', required=True)
    state_parser.add_argument('--track', required=True)
    state_parser.add_argument('--live', action='store_true')
    state_parser.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        if args.output:
            require(not os.path.lexists(args.output), '--output already exists; choose a new file')
        if args.command in {'snapshot', 'release-state'}:
            require(bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+', args.package)), 'Invalid package')
            if args.command == 'release-state':
                require(bool(args.track) and not any(c.isspace() or c in '/?#' for c in args.track), 'Use an exact API track identifier')
                result = ReleasePublisher(args.package, ADCTransport()).release_state(args.track) if args.live else {
                    'status': 'offline-read-plan', 'package_name': args.package, 'track': args.track,
                    'source': 'Android Publisher applications.tracks.releases.list', 'note': 'No credentials or network calls; use --live to read actual release lifecycle summaries without an edit'}
                if args.output:
                    write_json(Path(args.output), result)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            groups = None
            if args.language:
                for language in args.language:
                    locale(language)
                groups = [{'language': language, 'image_type': kind} for language in args.language for kind in args.image_type or sorted(IMAGE_TYPES)]
            require(not args.image_type or args.language, '--image-type requires --language')
            result = ReleasePublisher(args.package, ADCTransport()).snapshot(groups) if args.live else {'status': 'offline-read-plan', 'package_name': args.package, 'images': groups}
            if args.output:
                write_json(Path(args.output), result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        config_path = Path(args.config).resolve()
        config = json.loads(config_path.read_text(encoding='utf-8'))
        prepared = validate_config(config, config_path.parent)
        if args.command == 'plan' or not args.live:
            current = json.loads(Path(args.current).read_text()) if getattr(args, 'current', None) else None
            result = plan(config, config_path.parent, current)
        else:
            if getattr(args, 'current', None):
                raise ValueError('--current is offline-only; live takes a fresh snapshot')
            backup = args.backup_directory or str(Path('outputs/play-release-backups') / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(4)))
            if os.path.lexists(backup):
                raise FileExistsError('Backup directory already exists; choose a new path before creating an edit')
            client = ReleasePublisher(prepared['package_name'], ADCTransport())
            result = client.apply(config, directory=config_path.parent, backup_directory=backup, validate_only=args.command == 'validate')
        if args.output:
            try:
                write_json(Path(args.output), result)
            except OSError:
                if result.get('status') in {'committed', 'validated-only'}:
                    result['output_error'] = 'Confirmed result could not be exported; use stdout and backup receipt. Do not repeat commit.'
                else:
                    raise
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except PlayError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
