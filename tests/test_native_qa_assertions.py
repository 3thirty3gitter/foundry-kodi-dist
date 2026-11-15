import ast
import pathlib
import subprocess
import sys
import unittest
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE/'native_qa_assertions.py').exists() else HERE.parent/'tools'))
from native_qa_assertions import harden_qa_source

class Assertions(unittest.TestCase):
    def run_source(self, source, optimize='-O'):
        return subprocess.run([sys.executable, optimize, '-c', harden_qa_source(source)], capture_output=True, text=True)
    def test_failure_under_optimization(self):
        for flag in ('-O', '-OO'):
            r=self.run_source("assert False, 'sentinel'; print('BAD')",flag)
            self.assertNotEqual(r.returncode,0);self.assertIn('AssertionError: sentinel',r.stderr);self.assertNotIn('BAD',r.stdout)
    def test_pass_and_lazy_message(self):
        r=self.run_source("assert True, 1/0; print('PASS')")
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stdout.strip(),'PASS')
    def test_single_evaluation(self):
        r=self.run_source("calls=[]\ndef predicate():\n calls.append(1);return True\nassert predicate()\nprint(len(calls))")
        self.assertEqual(r.stdout.strip(),'1');self.assertEqual(r.returncode,0,r.stderr)
    def test_message_evaluated_only_on_failure(self):
        r=self.run_source("calls=[]\ndef msg():\n calls.append(1);return 'bad'\ntry:\n assert False,msg()\nexcept AssertionError as e: print(str(e),len(calls))")
        self.assertEqual(r.stdout.strip(),'bad 1');self.assertEqual(r.returncode,0,r.stderr)
    def test_nested_semicolon_and_no_message(self):
        r=self.run_source("def f():\n assert True; assert False\nf()")
        self.assertNotEqual(r.returncode,0);self.assertIn('AssertionError',r.stderr)
    def test_future_and_docstring(self):
        r=self.run_source('"doc"\nfrom __future__ import annotations\nassert False, "future"')
        self.assertIn('AssertionError: future',r.stderr)
    def test_shadowed_assertionerror(self):
        r=self.run_source("AssertionError=None\nassert False,'real builtin'")
        self.assertIn('AssertionError: real builtin',r.stderr)
    def test_alias_collision(self):
        r=self.run_source("_foundry_qa_assertions_builtins=0\nassert False,'collision'")
        self.assertIn('AssertionError: collision',r.stderr)
    def test_no_assert_byte_preserved(self):
        text='# preserve source receipts\nvalue = 1\n'
        self.assertEqual(harden_qa_source(text),text)
    def test_invalid_source_fails_closed(self):
        with self.assertRaises(SyntaxError):harden_qa_source('assert (')
    def test_idempotent(self):
        text=harden_qa_source('assert False')
        self.assertEqual(harden_qa_source(text),text)
        self.assertFalse(any(isinstance(n,ast.Assert) for n in ast.walk(ast.parse(text))))
if __name__=='__main__':unittest.main()
