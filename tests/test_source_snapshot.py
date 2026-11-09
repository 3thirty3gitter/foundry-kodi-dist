"""Batch source verification keeps exact binary/text equality with Git objects."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import snapshot_sources


class SnapshotObjects(unittest.TestCase):
    def test_binary_and_newline_bytes_are_preserved_exactly(self):
        values = {'a.txt': b'first\r\nsecond\n', 'b.bin': b'\0\xff\nblob\0'}
        payload = b''.join(b'abc123 blob ' + str(len(data)).encode() + b'\n' + data + b'\n'
                           for data in values.values())
        with patch.object(snapshot_sources.subprocess, 'check_output', return_value=payload) as read:
            self.assertEqual(snapshot_sources.committed_files(Path('source'), 'commit', values), values)
        self.assertEqual(read.call_count, 1)
        self.assertEqual(read.call_args.kwargs['input'], b'commit:a.txt\ncommit:b.bin\n')

    def test_missing_non_blob_truncated_and_extra_data_fail_closed(self):
        for payload in (b'', b'commit:a.txt missing\n', b'abc tree 1\nx\n',
                        b'abc blob 5\nx\n', b'abc blob 1\nx\nextra'):
            with self.subTest(payload=payload), patch.object(snapshot_sources.subprocess, 'check_output', return_value=payload):
                with self.assertRaises(ValueError):
                    snapshot_sources.committed_files(Path('source'), 'commit', ['a.txt'])

    def test_path_cannot_inject_another_batch_request(self):
        with patch.object(snapshot_sources.subprocess, 'check_output') as read:
            with self.assertRaises(ValueError):
                snapshot_sources.committed_files(Path('source'), 'commit', ['a\nb'])
        read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
