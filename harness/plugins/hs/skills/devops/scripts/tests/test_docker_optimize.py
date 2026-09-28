"""
Tests for docker-optimize.py

Run with: pytest test_docker_optimize.py -v

Kept to the cases that catch a documented real bug or a genuine security-relevant
finding; the class-by-class band coverage this file used to carry (one positive +
one negative test per analyze_* method) was ceremony — DockerfileAnalyzer is a
pure text/regex parser with no external tool to wrap, so those pairs only proved
the regex matches the exact string it was written against.
"""

import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from docker_optimize import DockerfileAnalyzer


@pytest.fixture
def temp_dockerfile(tmp_path):
    """Create temporary Dockerfile"""
    dockerfile = tmp_path / "Dockerfile"
    return dockerfile


def write_dockerfile(filepath, content):
    """Helper to write Dockerfile content"""
    with open(filepath, 'w') as f:
        f.write(content)


class TestAnalyzeAptCache:
    def test_apt_with_cleanup_on_continuation_line(self, temp_dockerfile):
        # A real-world RUN split across backslash-continuation lines: the
        # cleanup command lives on a DIFFERENT physical line than
        # `apt-get install`, but the same logical instruction. A per-physical-
        # line scanner reports a false-positive "not cleaned" suggestion here
        # even though the cleanup genuinely is present in the same layer.
        content = (
            "FROM ubuntu:22.04\n"
            "RUN apt-get update && \\\n"
            "    apt-get install -y curl && \\\n"
            "    rm -rf /var/lib/apt/lists/*\n"
        )
        write_dockerfile(temp_dockerfile, content)
        analyzer = DockerfileAnalyzer(temp_dockerfile)
        analyzer.load_dockerfile()
        analyzer.analyze_apt_cache()

        apt_suggestions = [s for s in analyzer.suggestions if 'apt cache' in s['message']]
        assert len(apt_suggestions) == 0, (
            "cleanup on a continuation line of the SAME RUN instruction must "
            "not be reported as missing"
        )


class TestAnalyzeSecurity:
    def test_detect_secrets(self, temp_dockerfile):
        content = """
FROM node:20
ENV API_KEY=secret123
ENV PASSWORD=mypassword
"""
        write_dockerfile(temp_dockerfile, content)
        analyzer = DockerfileAnalyzer(temp_dockerfile)
        analyzer.load_dockerfile()
        analyzer.analyze_security()

        secret_issues = [i for i in analyzer.issues
                        if i['category'] == 'security' and 'secret' in i['message'].lower()]
        assert len(secret_issues) >= 1


class TestIntegration:
    """Integration tests"""

    def test_full_analysis_workflow(self, temp_dockerfile):
        content = """
FROM python:3.11
COPY . /app
RUN pip install -r /app/requirements.txt
ENV API_KEY=secret
CMD ["python", "/app/app.py"]
"""
        write_dockerfile(temp_dockerfile, content)

        analyzer = DockerfileAnalyzer(temp_dockerfile, verbose=True)
        results = analyzer.analyze()

        # Verify all expected checks ran
        assert len(analyzer.issues) > 0
        assert len(analyzer.suggestions) > 0

        # Should flag multiple categories
        categories = {i['category'] for i in analyzer.issues}
        assert 'security' in categories

        # Verify summary calculations
        total_findings = (results['summary']['errors'] +
                         results['summary']['warnings'] +
                         results['summary']['suggestions'])
        assert total_findings > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
