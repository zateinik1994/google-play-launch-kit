"""Offline Publisher delivery tests: fake transports only, never Google."""
import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from shared.play_api import ADCTransport, APIError, PlayError
from shared.play_release import IMAGE_TYPES, ReleasePublisher, main, plan, validate_config
from test_validate_images import png

LISTING = {'en-US': {'title': 'Habits', 'shortDescription': 'Track your habits.', 'fullDescription': 'Create a daily checklist.'}}


class FakePublisher:
    def __init__(self, image_bytes=None, failure=None):
        self.image_bytes = image_bytes or png(1080, 1920)
        self.calls = []
        self.failure = failure
        self.listings = copy.deepcopy(LISTING)
        self.images = [{'id': 'one', 'url': 'https://lh3.googleusercontent.com/one', 'sha256': hashlib.sha256(self.image_bytes).hexdigest()},
                       {'id': 'two', 'url': 'https://lh3.googleusercontent.com/two', 'sha256': hashlib.sha256(self.image_bytes).hexdigest()}]
        self.version = 42
        self.backup = None

    def request(self, method, url, *, payload=None, query=None):
        self.calls.append((method, url, payload, query))
        if self.failure and url.endswith(self.failure[0]):
            raise self.failure[1]
        if method == 'POST' and url.endswith('/edits'):
            return {'id': 'edit-1'}
        if method == 'GET':
            if url.endswith('/listings'):
                return {'listings': [dict(v, language=k) for k, v in self.listings.items()]}
            if url.endswith('/tracks'):
                return {'tracks': [{'track': 'internal', 'releases': [{'status': 'completed', 'versionCodes': ['41']}]}, {'track': 'production', 'releases': []}, {'track': 'closed-beta', 'releases': []}]}
            if url.endswith('/details'):
                return {'defaultLanguage': 'en-US', 'contactEmail': 'old@example.com'}
            if url.endswith('/bundles'):
                return {'bundles': [{'versionCode': 41}]}
            return {'images': self.images if url.endswith('/phoneScreenshots') else []}
        if method in {'PUT', 'PATCH', 'DELETE'} and not url.endswith('/edit-1'):
            if self.backup is not None:
                assert (self.backup/'transaction.json').exists(), 'Missing durable transaction before write'
                assert (self.backup/'rollback.json').exists(), 'Missing rollback before write'
        if url.endswith(':commit'):
            return {'id': 'edit-1'}
        return {}

    def download_bytes(self, url, *, limit=None):
        self.calls.append(('DOWNLOAD', url, None, None))
        return self.image_bytes

    def upload_media(self, url, path, mime, *, resumable=False):
        self.calls.append(('UPLOAD', url, str(path), {'mime': mime, 'resumable': resumable}))
        if url.endswith('/bundles'):
            return {'versionCode': self.version}
        return {'image': {'id': 'new-' + str(len(self.calls))}}


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.asset = self.root/'phone.png'
        self.asset.write_bytes(png(1080, 1920))
        self.aab = self.root/'app.aab'
        with zipfile.ZipFile(self.aab, 'w') as archive:
            archive.writestr('BundleConfig.pb', b'config')
            archive.writestr('base/manifest/AndroidManifest.xml', b'protobuf manifest')
        self.backup = self.root/'backup'

    def tearDown(self):
        self.temp.cleanup()

    def config(self, **kwargs):
        return dict(package_name='com.example.habits', **kwargs)

    def image_config(self, operation='replace', **kwargs):
        operation_fields = kwargs or {'files': ['phone.png']}
        return self.config(images=[dict(language='en-US', image_type='phoneScreenshots', operation=operation, **operation_fields)])

    def apply(self, config, transport=None, validate_only=False):
        transport = transport or FakePublisher()
        transport.backup = self.backup
        client = ReleasePublisher('com.example.habits', transport)
        return client.apply(config, directory=self.root, backup_directory=self.backup, validate_only=validate_only), transport

    def test_library_config_package_must_match_client_before_any_api_call(self):
        transport = FakePublisher()
        client = ReleasePublisher('com.other.app', transport)
        with self.assertRaisesRegex(ValueError, 'differs from the Publisher client target'):
            client.apply(self.config(details={'contactWebsite':'https://example.com'}),
                         directory=self.root, backup_directory=self.backup)
        self.assertEqual(transport.calls, [])
        self.assertFalse(self.backup.exists())

    def test_replace_downloads_every_original_before_delete_and_upload(self):
        result, transport = self.apply(self.image_config())
        methods = [call[0] for call in transport.calls]
        delete = next(i for i,c in enumerate(transport.calls) if c[0] == 'DELETE' and c[1].endswith('/phoneScreenshots'))
        self.assertEqual(methods[:delete].count('DOWNLOAD'), 2)
        self.assertEqual(len(list(self.backup.glob('image-*.png'))), 2)
        self.assertEqual(result['status'], 'committed')
        self.assertNotEqual(transport.calls[-1][0], 'DELETE')
        upload = next(c for c in transport.calls if c[0] == 'UPLOAD')
        self.assertIn('/upload/androidpublisher/v3/', upload[1])
        self.assertEqual(transport.calls[-1][3], {'changesInReviewBehavior': 'ERROR_IF_IN_REVIEW'})

    def test_reorder_uses_complete_id_order_and_original_bytes(self):
        result, transport = self.apply(self.image_config('reorder', ids=['two', 'one']))
        uploads = [Path(c[2]).name for c in transport.calls if c[0] == 'UPLOAD']
        self.assertEqual(uploads, ['image-0-1.png', 'image-0-0.png'])
        self.assertEqual(result['status'], 'committed')

    def test_incomplete_reorder_never_deletes(self):
        transport = FakePublisher()
        with self.assertRaisesRegex(ValueError, 'every current image'):
            self.apply(self.image_config('reorder', ids=['one']), transport)
        self.assertFalse(any(c[0]=='UPLOAD' for c in transport.calls))
        self.assertEqual(transport.calls[-1][0], 'DELETE')
        self.assertTrue(transport.calls[-1][1].endswith('/edit-1'))

    def test_delete_specific_id_and_append_capacity(self):
        _, transport = self.apply(self.image_config('delete', ids=['one']))
        self.assertTrue(any(c[0]=='DELETE' and c[1].endswith('/phoneScreenshots/one') for c in transport.calls))
        self.assertFalse(any(c[0]=='UPLOAD' for c in transport.calls))
        self.backup = self.root/'append-backup'
        _, transport = self.apply(self.image_config('append'))
        self.assertFalse(any(c[0]=='DELETE' for c in transport.calls))

    def test_invalid_checksum_blocks_all_mutations(self):
        transport = FakePublisher()
        transport.images[0]['sha256'] = '0'*64
        with self.assertRaisesRegex(PlayError, 'checksum'):
            self.apply(self.image_config(), transport)
        self.assertFalse(any(c[0] in {'PUT','PATCH','UPLOAD'} for c in transport.calls))
        self.assertFalse(any(c[0]=='DELETE' and not c[1].endswith('/edit-1') for c in transport.calls))

    def test_backup_failure_stops_before_mutation(self):
        self.backup.mkdir()
        transport = FakePublisher()
        with self.assertRaises(FileExistsError):
            self.apply(self.image_config(), transport)
        self.assertFalse(any(c[0]=='UPLOAD' for c in transport.calls))

    def test_bundle_actual_version_and_explicit_retained_codes(self):
        config = self.config(bundle={'file':'app.aab','expected_version_code':42}, tracks=[{'track':'internal', 'releases':[{'status':'completed','versionCodes':['41','$uploaded'],'releaseNotes':[{'language':'en-US','text':'Faster checklist.'}]}]}])
        result, transport = self.apply(config)
        self.assertEqual(result['uploadedVersionCode'], 42)
        track = next(c[2] for c in transport.calls if c[0]=='PUT' and '/tracks/' in c[1])
        self.assertEqual(track['releases'][0]['versionCodes'], ['41','42'])
        self.assertTrue(next(c for c in transport.calls if c[0]=='UPLOAD')[3]['resumable'])

    def test_unexpected_bundle_version_never_updates_track_or_commits(self):
        with self.assertRaisesRegex(ValueError, 'differs from expected'):
            self.apply(self.config(bundle={'file':'app.aab','expected_version_code':43}))
        transaction=json.loads((self.backup/'transaction.json').read_text())
        self.assertEqual(transaction['status'], 'staging-failed')

    def test_confirmed_commit_survives_receipt_write_failure(self):
        from shared.play_release import receipt
        calls = []
        def failing_receipt(path, data):
            calls.append(data['status'])
            if data['status'] == 'committed':
                raise OSError('disk full')
            receipt(path, data)
        with patch('shared.play_release.receipt', side_effect=failing_receipt):
            result, transport = self.apply(self.image_config())
        self.assertEqual(result['status'], 'committed')
        self.assertIn('receipt_error', result)
        self.assertEqual(sum(c[1].endswith(':commit') for c in transport.calls), 1)

    def test_existing_output_blocks_live_before_credentials(self):
        config=self.root/'config.json';config.write_text(json.dumps(self.image_config()))
        output=self.root/'existing.json';output.write_text('{}')
        with patch('shared.play_release.ADCTransport',side_effect=AssertionError('network')), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['apply','--live','--config',str(config),'--output',str(output)]),2)

    def test_validate_only_stages_checks_and_discards(self):
        result, transport = self.apply(self.image_config(), validate_only=True)
        self.assertEqual(result['status'], 'validated-only')
        self.assertFalse(any(c[1].endswith(':commit') for c in transport.calls))
        self.assertTrue(transport.calls[-1][1].endswith('/edit-1'))

    def test_unknown_commit_receipt_and_no_retry(self):
        transport = FakePublisher(failure=(':commit', APIError(503,'Unavailable')))
        with self.assertRaisesRegex(PlayError, 'unknown'):
            self.apply(self.image_config(), transport)
        self.assertEqual(sum(c[1].endswith(':commit') for c in transport.calls), 1)
        self.assertEqual(json.loads((self.backup/'transaction.json').read_text())['status'], 'commit-outcome-unknown')

    def test_new_locale_is_written_before_image_and_rolls_back_by_delete(self):
        config=self.config(listings={'fr-FR':dict(LISTING['en-US'])},images=[{'language':'fr-FR','image_type':'phoneScreenshots','operation':'replace','files':['phone.png']}])
        _,transport=self.apply(config)
        self.assertLess(next(i for i,c in enumerate(transport.calls) if c[0]=='PUT'),next(i for i,c in enumerate(transport.calls) if c[0]=='UPLOAD'))
        rollback=json.loads((self.backup/'rollback.json').read_text())
        self.assertEqual(rollback['delete_listings'], ['fr-FR'])
        self.assertNotIn('images', rollback)
        validate_config(rollback)

    def test_deleting_locale_backs_up_all_its_images(self):
        _,transport=self.apply(self.config(delete_listings=['en-US']))
        self.assertEqual(sum(c[0]=='GET' and any(c[1].endswith('/'+kind) for kind in IMAGE_TYPES) for c in transport.calls),len(IMAGE_TYPES))
        self.assertEqual(len(list(self.backup.glob('image-*.png'))),2)
        rollback=json.loads((self.backup/'rollback.json').read_text())
        self.assertIn('en-US',rollback['listings'])
        validate_config(rollback)

    def test_contacts_patch_does_not_erase_omitted_fields(self):
        _,transport=self.apply(self.config(details={'contactWebsite':'https://example.com'}))
        request=next(c for c in transport.calls if c[0]=='PATCH')
        self.assertEqual(request[2],{'contactWebsite':'https://example.com'})
        self.assertEqual(json.loads((self.backup/'rollback.json').read_text())['details'],{'contactWebsite':''})

    def test_bad_track_or_notes_rejected_before_api(self):
        for release in [dict(status='inProgress',versionCodes=['42'],userFraction=1),dict(status='completed',versionCodes=['42'],userFraction=.1),dict(status='draft',versionCodes=['42'],releaseNotes=[{'language':'en-US','text':'x'*501}])]:
            transport=FakePublisher()
            with self.assertRaises(ValueError):
                self.apply(self.config(tracks=[{'track':'production','releases':[release]}]),transport)
            self.assertEqual(transport.calls,[])

    def test_exact_closed_track_and_empty_releases_are_supported(self):
        _,transport=self.apply(self.config(tracks=[{'track':'closed-beta','releases':[]}]))
        self.assertTrue(any(c[0]=='PUT' and c[1].endswith('/tracks/closed-beta') and c[2]['releases']==[] for c in transport.calls))

    def test_default_apply_and_snapshot_never_load_credentials(self):
        config=self.root/'config.json'
        config.write_text(json.dumps(self.image_config()))
        with patch('shared.play_release.ADCTransport',side_effect=AssertionError('network')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['apply','--config',str(config)]),0)
            self.assertEqual(main(['snapshot','--package','com.example.habits']),0)

    def test_tablet_upload_types_use_large_screen_validation_before_api(self):
        tablet = self.root/'tablet.png'
        tablet.write_bytes(png(4096, 2304))
        for image_type in ('sevenInchScreenshots', 'tenInchScreenshots'):
            with self.subTest(image_type=image_type):
                prepared = validate_config(self.config(images=[dict(language='en-US',image_type=image_type,operation='replace',files=['tablet.png'])]), self.root)
                self.assertEqual(prepared['images'][0]['files'][0]['mime'], 'image/png')
        with self.assertRaisesRegex(ValueError, 'Phone screenshot'):
            validate_config(self.config(images=[dict(language='en-US',image_type='phoneScreenshots',operation='replace',files=['tablet.png'])]), self.root)

    def test_tablet_wrong_size_or_alpha_rejected_without_transport_calls(self):
        for data in (png(320, 640), png(1440, 2560, color=6)):
            (self.root/'tablet.png').write_bytes(data)
            transport=FakePublisher()
            with self.assertRaises(ValueError):
                self.apply(self.config(images=[dict(language='en-US',image_type='sevenInchScreenshots',operation='replace',files=['tablet.png'])]), transport)
            self.assertEqual(transport.calls, [])

    def test_plan_matches_baseline_and_shows_track_before_after(self):
        config=self.config(tracks=[{'track':'production','releases':[{'status':'inProgress','versionCodes':['42'],'userFraction':.05}]}])
        result=plan(config,current={'package_name':'com.example.habits','tracks':[{'track':'production','releases':[]}]})
        self.assertEqual(result['changes']['tracks'][0]['from']['releases'],[])
        with self.assertRaisesRegex(ValueError,'package'):
            plan(config,current={'package_name':'wrong'})


class MediaTransportTests(unittest.TestCase):
    def transport(self, responses):
        calls=[]
        def request(method,url,**kwargs):
            calls.append((method,url,kwargs))
            return responses.pop(0)
        transport=ADCTransport.__new__(ADCTransport)
        transport.timeout=1
        transport.session=SimpleNamespace(request=request)
        return transport,calls

    def response(self, status=200, value=None, headers=None):
        return SimpleNamespace(status_code=status,content=b'' if value is None else b'json',headers=headers or {},json=lambda:value)

    def test_resumable_stream_uses_google_location_and_binary_headers(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'bundle.aab';path.write_bytes(b'zip')
            transport,calls=self.transport([self.response(headers={'Location':'https://androidpublisher.googleapis.com/upload/session?upload_id=private'}),self.response(201,{'versionCode':42})])
            self.assertEqual(transport.upload_media('https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/a/edits/e/bundles',path,'application/octet-stream',resumable=True)['versionCode'],42)
            self.assertEqual([c[0] for c in calls],['POST','PUT'])
            self.assertEqual(calls[1][2]['headers']['Content-Length'],'3')
            self.assertFalse(calls[1][2]['allow_redirects'])

    def test_unsafe_session_location_never_receives_bearer_or_body(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'bundle.aab';path.write_bytes(b'zip')
            transport,calls=self.transport([self.response(headers={'Location':'https://evil.example/session'})])
            with self.assertRaisesRegex(PlayError,'unsafe'):
                transport.upload_media('https://androidpublisher.googleapis.com/upload/a',path,'application/octet-stream',resumable=True)
            self.assertEqual(len(calls),1)

    def test_media_server_error_is_not_retried(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'image.png';path.write_bytes(b'png')
            transport,calls=self.transport([self.response(503)])
            with self.assertRaises(APIError):
                transport.upload_media('https://androidpublisher.googleapis.com/upload/a',path,'image/png')
            self.assertEqual(len(calls),1)

    def test_download_never_forwards_publisher_auth_and_blocks_redirect_host(self):
        class Response:
            status_code=302
            headers={'Location':'https://evil.example/asset'}
            def __enter__(self): return self
            def __exit__(self,*args): pass
        calls=[]
        def get(url, **kwargs):
            calls.append((url,kwargs));return Response()
        transport=ADCTransport.__new__(ADCTransport);transport.timeout=1
        with patch.dict('sys.modules',{'requests':SimpleNamespace(get=get)}):
            with self.assertRaisesRegex(PlayError,'approved'):
                transport.download_bytes('https://lh3.googleusercontent.com/original')
        self.assertEqual(len(calls),1)
        self.assertNotIn('headers',calls[0][1])
        self.assertFalse(calls[0][1]['allow_redirects'])

    def test_download_bytes_enforces_stream_limit(self):
        class Response:
            status_code=200
            headers={}
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def iter_content(self,size): yield b'x'*20
        transport=ADCTransport.__new__(ADCTransport);transport.timeout=1
        with patch.dict('sys.modules',{'requests':SimpleNamespace(get=lambda *a,**k:Response())}):
            with self.assertRaisesRegex(PlayError,'limit'):
                transport.download_bytes('https://lh3.googleusercontent.com/original',limit=10)


if __name__ == '__main__':
    unittest.main()
