'''Tests for presence noise filter.'''

import json
import tempfile
import unittest
from pathlib import Path

import presence_filter as pf

class FilterTest(unittest.TestCase):
    def test_noise_heartbeat(self):
        r = pf.classify_post('heartbeat layer online, still here')
        self.assertEqual(r['label'], 'presence_noise')

    def test_noise_ed25519_without_payload(self):
        r = pf.classify_post('signed presence Ed25519 verification ok')
        self.assertEqual(r['label'], 'presence_noise')
        self.assertFalse(r['has_json'])

    def test_continuity_signal(self):
        txt = 'continuity check-in did:key:z6Mkaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa request id 42'
        r = pf.classify_post(txt)
        self.assertEqual(r['label'], 'substantive')
        self.assertEqual(r['category'], 'continuity')
        self.assertEqual(len(r['dids']), 1)
        self.assertTrue(r['dids'][0]['valid'])

    def test_telemetry_signal(self):
        r = pf.classify_post('VPS telemetry uptime 12 days RAM 2GB load average 0.1')
        self.assertEqual(r['label'], 'substantive')
        self.assertEqual(r['category'], 'telemetry')

    def test_tuning_signal(self):
        r = pf.classify_post('tip: long-poll wait 10 with cursors cuts read load')
        self.assertEqual(r['label'], 'substantive')
        self.assertEqual(r['category'], 'tuning_tip')

    def test_json_payload_signal(self):
        txt = json.dumps({'did': 'x', 'uptime': 'ok'})
        r = pf.classify_post(txt)
        self.assertEqual(r['label'], 'substantive')
        self.assertTrue(r['has_json'])

    def test_normalize_collapses(self):
        a = pf.normalize_text('Heartbeat Layer ONLINE!!!')
        b = pf.normalize_text('heartbeat  layer online')
        self.assertEqual(a, b)
        self.assertEqual(pf.text_hash(a), pf.text_hash(b))

    def test_cluster_groups_duplicates(self):
        posts = [
            {'seq': 1, 'room': 'technocore', 'text': 'heartbeat layer online'},
            {'seq': 2, 'room': 'technocore', 'text': 'Heartbeat layer online!!'},
            {'seq': 3, 'room': 'technocore', 'text': 'VPS telemetry uptime ok RAM ok'},
        ]
        clusters = pf.cluster_posts(posts)
        self.assertEqual(len(clusters), 2)
        top = clusters[0]
        self.assertEqual(top['count'], 2)

    def test_did_checker(self):
        good = 'did:key:z6Mkaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        bad_short = 'did:key:z6Mk'
        self.assertTrue(pf.did_is_valid(good))
        self.assertFalse(pf.did_is_valid(bad_short))
        self.assertFalse(pf.did_is_valid('did:key:bad'))
        found = pf.find_dids('see ' + good + ' here')
        self.assertEqual(len(found), 1)

    def test_parse_pipe_and_json(self):
        line2 = json.dumps({'seq': 16837539, 'room': 'technocore', 'text': 'VPS telemetry uptime ok'})
        lines = [
            '16837528|technocore|continuity check-in request id 1',
            line2,
            'plain heartbeat layer online',
        ]
        posts = pf.parse_log_lines(lines)
        self.assertEqual(len(posts), 3)
        self.assertEqual(posts[0]['seq'], 16837528)
        self.assertEqual(posts[1]['seq'], 16837539)

    def test_summary_and_markdown_file(self):
        lines = [
            '1|technocore|heartbeat layer online',
            '2|technocore|heartbeat layer online',
            '3|technocore|continuity check-in request id 7 did:key:z6Mkaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            '4|technocore|VPS telemetry uptime 5 days RAM ok load average 0.2',
        ]
        posts = pf.parse_log_lines(lines)
        classified = pf.classify_all(posts)
        clusters = pf.cluster_posts(posts)
        summary = pf.summarize(classified, clusters)
        self.assertEqual(summary['total'], 4)
        self.assertEqual(summary['noise'], 2)
        self.assertEqual(summary['signal'], 2)
        with tempfile.TemporaryDirectory() as td:
            out = str(Path(td) / 'review.md')
            pf.write_markdown_summary(summary, pf.surface_substantive(classified), clusters, out)
            data = Path(out).read_text(encoding='utf-8')
            self.assertIn('Substantive posts', data)
            self.assertIn('seq 3', data)

    def test_parse_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / 'log.txt'
            txt = '1|technocore|heartbeat layer online' + chr(10) + '2|technocore|tip long-poll wait 10 cursor' + chr(10)
            inp.write_text(txt, encoding='utf-8')
            posts = pf.parse_log_file(str(inp))
            self.assertEqual(len(posts), 2)
            classified = pf.classify_all(posts)
            self.assertEqual(classified[0]['label'], 'presence_noise')
            self.assertEqual(classified[1]['label'], 'substantive')

if __name__ == '__main__':
    unittest.main()
