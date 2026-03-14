#!/usr/bin/env python3
"""Tests for evidence_store.py, dedup.py, and page_cache.py.

Uses only stdlib unittest (pytest-compatible) — no external packages.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

# Add scripts dir to path
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from dedup import normalize_url, url_hash, is_duplicate

EVIDENCE_STORE = os.path.join(SCRIPTS_DIR, "evidence_store.py")


def run_cmd(*args: str) -> subprocess.CompletedProcess:
    """Run evidence_store.py with given arguments."""
    return subprocess.run(
        [sys.executable, EVIDENCE_STORE, *args],
        capture_output=True,
        text=True,
    )


class TestURLNormalization(unittest.TestCase):
    """URL normalization edge cases."""

    def test_lowercase_scheme_and_host(self):
        assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"

    def test_strip_www(self):
        assert normalize_url("https://www.example.com/page") == "https://example.com/page"

    def test_trailing_slash(self):
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_root_path_preserved(self):
        result = normalize_url("https://example.com/")
        assert result == "https://example.com/"

    def test_strip_utm_params(self):
        url = "https://example.com/page?utm_source=twitter&utm_medium=social&key=val"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "key=val" in result

    def test_strip_fbclid(self):
        url = "https://example.com/page?fbclid=abc123&real=yes"
        result = normalize_url(url)
        assert "fbclid" not in result
        assert "real=yes" in result

    def test_strip_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_empty_url(self):
        assert normalize_url("") == ""

    def test_combined_normalization(self):
        """www + trailing slash + tracking params + fragment."""
        url = "HTTPS://WWW.Example.Com/path/?utm_source=x&real=1#frag"
        result = normalize_url(url)
        assert result == "https://example.com/path?real=1"

    def test_port_preserved_non_default(self):
        result = normalize_url("https://example.com:8443/api")
        assert ":8443" in result

    def test_default_port_stripped(self):
        # urlparse handles default ports, but explicit 443 for https
        result = normalize_url("https://example.com:443/api")
        assert ":443" not in result


class TestURLHash(unittest.TestCase):
    def test_hash_length(self):
        h = url_hash("https://example.com")
        assert len(h) == 12

    def test_consistent(self):
        h1 = url_hash("https://example.com/page")
        h2 = url_hash("https://example.com/page")
        assert h1 == h2

    def test_normalized_same_hash(self):
        h1 = url_hash("https://www.example.com/page/")
        h2 = url_hash("https://example.com/page")
        assert h1 == h2

    def test_different_urls_different_hash(self):
        h1 = url_hash("https://example.com/a")
        h2 = url_hash("https://example.com/b")
        assert h1 != h2


class TestIsDuplicate(unittest.TestCase):
    def test_duplicate(self):
        existing = ["https://example.com/page", "https://other.com"]
        assert is_duplicate("https://www.example.com/page/", existing)

    def test_not_duplicate(self):
        existing = ["https://example.com/page"]
        assert not is_duplicate("https://example.com/other", existing)


class TestEvidenceStoreInit(unittest.TestCase):
    def test_init_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_cmd("init", tmpdir)
            assert result.returncode == 0, result.stderr

            edir = os.path.join(tmpdir, "evidence")
            assert os.path.isdir(edir)
            assert os.path.isdir(os.path.join(edir, "pages"))

            for fname in ["sources.json", "claims.json", "hypotheses.json", "scope.json", "search_log.json"]:
                path = os.path.join(edir, fname)
                assert os.path.exists(path), f"Missing {fname}"
                with open(path) as f:
                    data = json.load(f)
                assert data is not None

    def test_init_idempotent(self):
        """Running init twice doesn't overwrite existing data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_cmd("init", tmpdir)
            # Add some data
            sources_path = os.path.join(tmpdir, "evidence", "sources.json")
            with open(sources_path, "w") as f:
                json.dump({"s_test": {"url": "test"}}, f)
            # Run init again
            run_cmd("init", tmpdir)
            with open(sources_path) as f:
                data = json.load(f)
            assert "s_test" in data


class TestAddSource(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        run_cmd("init", self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_add_source_basic(self):
        result = run_cmd(
            "add-source", self.tmpdir,
            "--url", "https://example.com/article",
            "--title", "Test Article",
            "--snippet", "A test snippet.",
        )
        assert result.returncode == 0
        sid = result.stdout.strip()
        assert sid.startswith("s_")
        assert len(sid) == 14  # s_ + 12 chars

        with open(os.path.join(self.tmpdir, "evidence", "sources.json")) as f:
            sources = json.load(f)
        assert sid in sources
        assert sources[sid]["title"] == "Test Article"
        assert sources[sid]["rating"] is None

    def test_add_source_dedup(self):
        """Adding same URL twice returns same ID, doesn't duplicate."""
        r1 = run_cmd(
            "add-source", self.tmpdir,
            "--url", "https://example.com/article",
            "--title", "First",
            "--snippet", "First snippet.",
        )
        r2 = run_cmd(
            "add-source", self.tmpdir,
            "--url", "https://www.example.com/article/",  # normalized same
            "--title", "Second",
            "--snippet", "Second snippet.",
        )
        assert r1.stdout.strip() == r2.stdout.strip()

        with open(os.path.join(self.tmpdir, "evidence", "sources.json")) as f:
            sources = json.load(f)
        # Should have exactly one entry
        assert len(sources) == 1
        # Title should be from first add (dedup skips update)
        sid = r1.stdout.strip()
        assert sources[sid]["title"] == "First"

    def test_add_source_with_optional_fields(self):
        result = run_cmd(
            "add-source", self.tmpdir,
            "--url", "https://nature.com/article",
            "--title", "Nature Article",
            "--snippet", "Snippet text",
            "--source-type", "academic",
            "--wave", "2",
            "--search-query", "quantum computing",
            "--publication-date", "2025-11-15",
            "--authors", '["Smith, J.", "Lee, K."]',
        )
        assert result.returncode == 0
        sid = result.stdout.strip()

        with open(os.path.join(self.tmpdir, "evidence", "sources.json")) as f:
            sources = json.load(f)
        s = sources[sid]
        assert s["source_type"] == "academic"
        assert s["wave"] == 2
        assert s["authors"] == ["Smith, J.", "Lee, K."]


class TestUpdateRating(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        run_cmd("init", self.tmpdir)
        result = run_cmd(
            "add-source", self.tmpdir,
            "--url", "https://example.com/rated",
            "--title", "Rated Source",
            "--snippet", "Snippet.",
        )
        self.sid = result.stdout.strip()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_update_rating(self):
        result = run_cmd(
            "update-rating", self.tmpdir,
            "--source-id", self.sid,
            "--reliability", "A",
            "--credibility", "2",
            "--rationale", "Peer-reviewed journal",
        )
        assert result.returncode == 0

        with open(os.path.join(self.tmpdir, "evidence", "sources.json")) as f:
            sources = json.load(f)
        rating = sources[self.sid]["rating"]
        assert rating["reliability"] == "A"
        assert rating["credibility"] == 2
        assert rating["rationale"] == "Peer-reviewed journal"

    def test_update_rating_with_bias_flags(self):
        result = run_cmd(
            "update-rating", self.tmpdir,
            "--source-id", self.sid,
            "--reliability", "C",
            "--credibility", "4",
            "--bias-flags", '["industry_funded", "potential_conflict"]',
        )
        assert result.returncode == 0

        with open(os.path.join(self.tmpdir, "evidence", "sources.json")) as f:
            sources = json.load(f)
        assert sources[self.sid]["rating"]["bias_flags"] == ["industry_funded", "potential_conflict"]

    def test_update_rating_nonexistent_source(self):
        result = run_cmd(
            "update-rating", self.tmpdir,
            "--source-id", "s_nonexistent",
            "--reliability", "A",
            "--credibility", "1",
        )
        assert result.returncode != 0


class TestAddClaim(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        run_cmd("init", self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_add_claim_basic(self):
        result = run_cmd(
            "add-claim", self.tmpdir,
            "--text", "The sky is blue",
            "--source-ids", '["s_abc123"]',
        )
        assert result.returncode == 0
        cid = result.stdout.strip()
        assert cid == "c_0001"

        with open(os.path.join(self.tmpdir, "evidence", "claims.json")) as f:
            claims = json.load(f)
        assert cid in claims
        assert claims[cid]["text"] == "The sky is blue"
        assert claims[cid]["supporting_source_ids"] == ["s_abc123"]

    def test_add_claim_sequential_ids(self):
        run_cmd("add-claim", self.tmpdir, "--text", "Claim 1", "--source-ids", '["s_a"]')
        run_cmd("add-claim", self.tmpdir, "--text", "Claim 2", "--source-ids", '["s_b"]')
        r3 = run_cmd("add-claim", self.tmpdir, "--text", "Claim 3", "--source-ids", '["s_c"]')
        assert r3.stdout.strip() == "c_0003"

    def test_add_claim_with_category_and_confidence(self):
        result = run_cmd(
            "add-claim", self.tmpdir,
            "--text", "Test claim",
            "--source-ids", '["s_x"]',
            "--category", "technical_milestone",
            "--confidence", "high",
        )
        cid = result.stdout.strip()
        with open(os.path.join(self.tmpdir, "evidence", "claims.json")) as f:
            claims = json.load(f)
        assert claims[cid]["category"] == "technical_milestone"
        assert claims[cid]["confidence"] == "high"


class TestHypothesesAndACH(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        run_cmd("init", self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_add_hypothesis(self):
        result = run_cmd("add-hypothesis", self.tmpdir, "--text", "Hypothesis A is true")
        assert result.returncode == 0
        hid = result.stdout.strip()
        assert hid == "h_001"

        with open(os.path.join(self.tmpdir, "evidence", "hypotheses.json")) as f:
            hyps = json.load(f)
        assert hid in hyps
        assert hyps[hid]["status"] == "active"

    def test_update_assessment(self):
        run_cmd("add-hypothesis", self.tmpdir, "--text", "H1")
        result = run_cmd(
            "update-assessment", self.tmpdir,
            "--hypothesis-id", "h_001",
            "--claim-id", "c_0001",
            "--assessment", "consistent",
        )
        assert result.returncode == 0

        with open(os.path.join(self.tmpdir, "evidence", "hypotheses.json")) as f:
            hyps = json.load(f)
        assert hyps["h_001"]["evidence_assessments"]["c_0001"] == "consistent"

    def test_update_assessment_invalid(self):
        run_cmd("add-hypothesis", self.tmpdir, "--text", "H1")
        result = run_cmd(
            "update-assessment", self.tmpdir,
            "--hypothesis-id", "h_001",
            "--claim-id", "c_0001",
            "--assessment", "maybe",
        )
        assert result.returncode != 0


class TestGetUnrated(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        run_cmd("init", self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_get_unrated(self):
        # Add two sources
        r1 = run_cmd("add-source", self.tmpdir, "--url", "https://a.com", "--title", "A", "--snippet", "s")
        r2 = run_cmd("add-source", self.tmpdir, "--url", "https://b.com", "--title", "B", "--snippet", "s")
        sid1, sid2 = r1.stdout.strip(), r2.stdout.strip()

        # Rate one
        run_cmd("update-rating", self.tmpdir, "--source-id", sid1, "--reliability", "A", "--credibility", "1")

        # Get unrated
        result = run_cmd("get-unrated", self.tmpdir)
        unrated = json.loads(result.stdout)
        assert sid2 in unrated
        assert sid1 not in unrated


class TestGetByRating(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        run_cmd("init", self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_get_by_rating_filters(self):
        # Add sources with different ratings
        urls = [
            ("https://a.com", "A"),
            ("https://b.com", "B"),
            ("https://c.com", "C"),
            ("https://d.com", "D"),
            ("https://e.com", "E"),
        ]
        sids = []
        for url, _ in urls:
            r = run_cmd("add-source", self.tmpdir, "--url", url, "--title", "T", "--snippet", "s")
            sids.append(r.stdout.strip())
        for sid, (_, rating) in zip(sids, urls):
            run_cmd("update-rating", self.tmpdir, "--source-id", sid, "--reliability", rating, "--credibility", "3")

        # Get C and above
        result = run_cmd("get-by-rating", self.tmpdir, "--min-reliability", "C")
        filtered = json.loads(result.stdout)
        assert len(filtered) == 3  # A, B, C
        # D and E should not be included
        for sid, (_, rating) in zip(sids, urls):
            if rating in ("A", "B", "C"):
                assert sid in filtered
            else:
                assert sid not in filtered


class TestGetUncorroborated(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        run_cmd("init", self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_uncorroborated_default(self):
        # Claim with 1 source (< 3 default)
        run_cmd("add-claim", self.tmpdir, "--text", "Weak claim", "--source-ids", '["s_a"]')
        # Claim with 3 sources
        run_cmd("add-claim", self.tmpdir, "--text", "Strong claim", "--source-ids", '["s_a", "s_b", "s_c"]')

        result = run_cmd("get-uncorroborated", self.tmpdir)
        uncorr = json.loads(result.stdout)
        assert "c_0001" in uncorr
        assert "c_0002" not in uncorr

    def test_uncorroborated_custom_threshold(self):
        run_cmd("add-claim", self.tmpdir, "--text", "C1", "--source-ids", '["s_a"]')
        run_cmd("add-claim", self.tmpdir, "--text", "C2", "--source-ids", '["s_a", "s_b"]')

        result = run_cmd("get-uncorroborated", self.tmpdir, "--min-sources", "2")
        uncorr = json.loads(result.stdout)
        assert "c_0001" in uncorr
        assert "c_0002" not in uncorr


class TestLogSearch(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        run_cmd("init", self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_log_search(self):
        result = run_cmd(
            "log-search", self.tmpdir,
            "--query", "quantum computing 2025",
            "--results-count", "15",
            "--wave", "1",
        )
        assert result.returncode == 0

        with open(os.path.join(self.tmpdir, "evidence", "search_log.json")) as f:
            log = json.load(f)
        assert len(log) == 1
        assert log[0]["query"] == "quantum computing 2025"
        assert log[0]["results_count"] == 15


class TestStats(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        run_cmd("init", self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_stats_aggregation(self):
        # Add sources
        r1 = run_cmd("add-source", self.tmpdir, "--url", "https://a.com", "--title", "A", "--snippet", "s")
        r2 = run_cmd("add-source", self.tmpdir, "--url", "https://b.com", "--title", "B", "--snippet", "s")
        sid1, sid2 = r1.stdout.strip(), r2.stdout.strip()

        # Rate one
        run_cmd("update-rating", self.tmpdir, "--source-id", sid1, "--reliability", "A", "--credibility", "1")

        # Add claims
        run_cmd("add-claim", self.tmpdir, "--text", "C1", "--source-ids", '["s_a"]', "--confidence", "high")
        run_cmd("add-claim", self.tmpdir, "--text", "C2", "--source-ids", '["s_a", "s_b", "s_c"]', "--confidence", "low")

        # Add hypothesis
        run_cmd("add-hypothesis", self.tmpdir, "--text", "H1")

        # Log search
        run_cmd("log-search", self.tmpdir, "--query", "test", "--results-count", "5", "--wave", "1")

        # Get stats
        result = run_cmd("stats", self.tmpdir)
        stats = json.loads(result.stdout)

        assert stats["sources_total"] == 2
        assert stats["sources_rated"] == 1
        assert stats["sources_unrated"] == 1
        assert stats["claims_total"] == 2
        assert stats["hypotheses_total"] == 1
        assert stats["searches_total"] == 1
        assert stats["rating_distribution"]["A"] == 1
        assert stats["claims_by_confidence"]["high"] == 1
        assert stats["claims_by_confidence"]["low"] == 1
        assert stats["claims_uncorroborated"] == 1  # C1 has only 1 source


class TestAtomicWrite(unittest.TestCase):
    """Test that atomic write doesn't corrupt on normal operation."""

    def test_no_tmp_file_left(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_cmd("init", tmpdir)
            run_cmd("add-source", tmpdir, "--url", "https://test.com", "--title", "T", "--snippet", "S")

            edir = os.path.join(tmpdir, "evidence")
            # No .tmp files should remain
            for fname in os.listdir(edir):
                assert not fname.endswith(".tmp"), f"Temp file left behind: {fname}"

    def test_data_survives_multiple_writes(self):
        """Multiple sequential writes don't lose data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_cmd("init", tmpdir)
            for i in range(10):
                run_cmd(
                    "add-source", tmpdir,
                    "--url", f"https://example{i}.com/article",
                    "--title", f"Article {i}",
                    "--snippet", f"Snippet {i}",
                )
            with open(os.path.join(tmpdir, "evidence", "sources.json")) as f:
                sources = json.load(f)
            assert len(sources) == 10


if __name__ == "__main__":
    unittest.main()
