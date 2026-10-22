"""Adapt sibling oracle/property intentions to the learned decoder's flat output.

Characterisation checks honour eight-character display truncation. Malformed packets must be dropped; valid packets after them must survive.
CR/LF noise outside complete packets remains covered. These are
ordinary failing tests, not expected-failure exemptions.
"""
import os
import random
import subprocess
import unittest
from pathlib import Path

import yaml
from hypothesis import given, settings, strategies as st

# Resolve paths from this file so IDE runners may use tests/ as their working directory.
ROOT = Path(__file__).resolve().parents[1]
EXE = (ROOT / os.environ.get("TITAN_EXE", "build-autotests/recode")).resolve()
settings.register_profile("archive", max_examples=int(os.environ.get("HYPOTHESIS_MAX_EXAMPLES", 100)), deadline=None, derandomize=True)
settings.load_profile("archive")


def invoke(data, *args):
    """Bound each process so malformed input cannot hang the suite."""
    return subprocess.run([str(EXE), *args], input=data, capture_output=True, timeout=3)


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys rather than silently overwrite earlier fields."""


def mapping(loader, node, deep=False):
    result = {}
    for k, v in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = loader.construct_object(v, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def records(data):
    result = invoke(data)
    assert result.returncode == 0, (result.returncode, result.stderr)
    value = yaml.load(result.stdout, Loader=UniqueLoader)
    if value is None:
        return []
    assert isinstance(value, list) and all(isinstance(x, dict) for x in value), value
    return value


class OutputTests(unittest.TestCase):
    def test_loader(self):
        """Check that the test oracle detects duplicate mapping keys."""
        with self.assertRaises(ValueError):
            yaml.load("- a: 1\n  a: 2", Loader=UniqueLoader)

    def test_ping(self):
        """Anchor the flat schema to independently written known values."""
        self.assertEqual(records(b"$1;2;152;;|"), [{"commandID": 1,
            "interpreted_command": "Ping", "sequence_number": 2,
            "timestamp": 152, "payload_hex": "3B"}])

    def test_ping_payload(self):
        """Accept opaque ping payloads and display their bounded hexadecimal preview."""
        for payload in (b"unexpected", b"\x00\x01\x7f\x80\xff;", b"A"*32, b"A"*33):
            with self.subTest(payload=payload):
                result = records(b"$1;2;3;" + payload + b"|$1;4;5;;|")
                self.assertEqual(len(result), 2)
                self.assertEqual(result[0]["interpreted_command"], "Ping")
                expected = payload[:32].hex(" ").upper()
                if len(payload) > 32:
                    expected += " ..."
                self.assertEqual(result[0]["payload_hex"], expected)
                self.assertEqual(result[1]["sequence_number"], 4)

    def test_housekeeping(self):
        """Preserve signed payload values and both accepted housekeeping IDs."""
        for command in (10, 12):
            with self.subTest(command=command):
                r = records(f"${command};1;2;0;12000;-9000;68;-29950;|".encode())[0]
                for key, value in zip(("status", "theta", "phi", "intensity", "temperature"),
                                      (0, 12000, -9000, 68, -29950)):
                    self.assertEqual(r["housekeeping_" + key], value)

    @given(st.integers(0, 99999999), st.integers(0, 99999999))
    def test_generated_ping(self, sequence, timestamp):
        """Round-trip headers across the entire untruncated display range."""
        r = records(f"$1;{sequence};{timestamp};;|".encode())[0]
        self.assertEqual((r["sequence_number"], r["timestamp"]), (sequence, timestamp))

    @given(st.lists(st.integers(-9999999, 9999999), min_size=4, max_size=4))
    def test_generated_housekeeping(self, values):
        """Generated signed fields must stay in the correct destinations."""
        packet = "$10;2;3;0;" + ";".join(map(str, values)) + ";|"
        r = records(packet.encode())[0]
        self.assertEqual([r["housekeeping_" + k] for k in
                          ("theta", "phi", "intensity", "temperature")], values)

    def test_newline_noise(self):
        """Ignore CR/LF outside complete packets without changing their records."""
        packet = b"$10;2;3;0;-4;5;6;-7;|"
        expected = records(packet)
        for noise in (b"\n", b"\r", b"\r\n"):
            with self.subTest(noise=noise):
                actual = records(noise + packet + noise + packet + noise)
                self.assertEqual(actual, expected + expected)

    def test_malformed_dropped(self):
        """Drop malformed and incomplete packets, then recover the next valid packet."""
        for packet in (b"$|", b"$x;2;3;|", b"$1;2;", b"$10;2;3;0;bad;|",
                       b"$1;-1;2;;|", b"$99;2;3;|",
                       b"$10;2;3;0;1;2;3;4;5;|"):
            with self.subTest(packet=packet):
                result = records(packet + b"$1;4;5;;|")
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["sequence_number"], 4)

    def test_each_binary_byte(self):
        """Each non-delimiter byte in a numeric field must be rejected unless decimal."""
        for byte in range(256):
            if byte in b"0123456789$|\r\n":
                continue
            with self.subTest(byte=byte):
                r = records(b"$1;"+bytes([byte])+b";3;;|")
                self.assertEqual(r, [])

    @given(st.binary(max_size=2048))
    def test_arbitrary_binary(self, data):
        """Brutal arbitrary bytes must terminate and emit parseable, control-safe YAML."""
        result = invoke(data)
        self.assertIn(result.returncode, (0, 1))
        self.assertFalse(any(b < 32 and b not in (9, 10, 13) for b in result.stdout))
        yaml.load(result.stdout, Loader=UniqueLoader)

    @given(st.binary(max_size=256))
    def test_binary_recovery(self, noise):
        """A known good packet after arbitrary bytes must still be recovered."""
        r = records(noise + b"$1;765;432;;|")
        self.assertEqual(r[-1]["sequence_number"], 765)

    def test_truncation_yaml(self):
        """Display truncation must not accidentally remove YAML's required key spacing."""
        for value in (12345678, 123456789, -1234567, -123456789):
            with self.subTest(value=value):
                r = records(f"$10;2;3;0;1;2;{value};{value};|".encode())[0]
                self.assertEqual(r["housekeeping_intensity"], int(str(value)[-8:]))

    def test_capture(self):
        """The supplied capture must yield one record per complete delimited packet."""
        data = (ROOT / "data/titan-protocol-capture.txt").read_bytes()
        self.assertEqual(len(records(data)), data.count(b"|"))

    def test_input_mutations(self):
        """Delete, insert, replace and flip bytes; a trailing good packet must survive."""
        packet = b"$10;2;3;0;-4;5;6;-7;|"
        rng = random.Random(20261021)
        cases = []
        for i in range(len(packet)):
            cases += [packet[:i]+packet[i+1:],
                      packet[:i]+bytes([rng.randrange(256)])+packet[i:],
                      packet[:i]+bytes([packet[i] ^ 128])+packet[i+1:]]
        for index, case in enumerate(cases):
            with self.subTest(index=index):
                r = records(case+b"$1;765;432;;|")
                self.assertEqual(r[-1]["sequence_number"], 765)

    def test_oversized_recovery(self):
        """Drop oversized packets and recover the following valid packet."""
        result = invoke(b"$" + b"A"*16386 + b"|$1;4;5;;|")
        # The current API may signal oversize as a nonzero exit; inspect its output anyway.
        r = yaml.load(result.stdout, Loader=UniqueLoader)
        self.assertIsInstance(r, list)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["sequence_number"], 4)

    def test_locale(self):
        """Available process locales must not alter numeric serialization."""
        locales = subprocess.check_output(["locale", "-a"], text=True).splitlines()
        data = b"$10;2;3;0;-1234;5678;6;-7;|"
        expected = invoke(data).stdout
        for locale in locales:
            with self.subTest(locale=locale):
                result = subprocess.run([str(EXE)], input=data, capture_output=True,
                    timeout=3, env=dict(os.environ, LC_ALL=locale))
                self.assertEqual(result.stdout, expected)

    def test_cli_arguments(self):
        """Reject extra CLI arguments rather than interpreting them as input paths."""
        self.assertNotEqual(invoke(b"", "unexpected").returncode, 0)

    def test_closed_stdin(self):
        """A failed POSIX read must produce a nonzero CLI exit status."""
        result = subprocess.run([str(EXE)], preexec_fn=lambda: os.close(0), capture_output=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)

    def test_full_output_device(self):
        """An ENOSPC write must not be reported as successful conversion."""
        with open("/dev/full", "wb") as sink:
            result = subprocess.run([str(EXE)], input=b"$1;2;3;;|", stdout=sink, timeout=3)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
