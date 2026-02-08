"""HTML report generator using Jinja2 templates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.results import TestResults


# ---------------------------------------------------------------------------
# Built-in HTML template (no external template file needed)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Voice Test Report — {{ title }}</title>
<style>
  :root { --bg: #F5F3EE; --card: #fff; --accent: #e94560; --text: #1a1a2e; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', system-ui, sans-serif; background: var(--bg);
         color: var(--text); line-height: 1.6; }
  .container { max-width: 960px; margin: 0 auto; padding: 24px; }
  header { background: var(--text); color: #fff; padding: 32px 0;
           border-bottom: 4px solid var(--accent); margin-bottom: 24px; }
  header h1 { font-size: 24px; font-weight: 700; }
  header .meta { font-size: 13px; color: #aaa; margin-top: 6px; }
  .card { background: var(--card); border-radius: 12px; padding: 20px;
          border: 1px solid #e0ddd5; margin-bottom: 20px; }
  .card h2 { font-size: 16px; margin-bottom: 12px; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px;
           font-size: 12px; font-weight: 600; }
  .badge.pass { background: #d4edda; color: #155724; }
  .badge.fail { background: #f8d7da; color: #721c24; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #eee; }
  th { font-weight: 600; color: #666; }
  .score { font-size: 28px; font-weight: 700; }
  .dimension { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
               gap: 14px; }
  .dim-card { padding: 16px; border-radius: 10px; background: #f9f7f2;
              border: 1px solid #e8e4db; }
  .dim-card .label { font-size: 12px; color: #888; }
  .dim-card .value { font-size: 22px; font-weight: 700; margin-top: 4px; }
</style>
</head>
<body>
<header>
  <div class="container">
    <h1>{{ title }}</h1>
    <div class="meta">Generated {{ timestamp }} &middot; {{ total_scenarios }} scenario(s)</div>
  </div>
</header>
<div class="container">
  <!-- Summary -->
  <div class="card">
    <h2>Summary</h2>
    <div class="dimension">
      <div class="dim-card">
        <div class="label">Total</div>
        <div class="value">{{ total_scenarios }}</div>
      </div>
      <div class="dim-card">
        <div class="label">Passed</div>
        <div class="value" style="color: #155724;">{{ passed }}</div>
      </div>
      <div class="dim-card">
        <div class="label">Failed</div>
        <div class="value" style="color: #721c24;">{{ failed }}</div>
      </div>
      <div class="dim-card">
        <div class="label">Pass Rate</div>
        <div class="value">{{ pass_rate }}%</div>
      </div>
    </div>
  </div>

  <!-- Dimension scores -->
  <div class="card">
    <h2>Evaluation Dimensions</h2>
    <div class="dimension">
      {% for name, score in dimensions.items() %}
      <div class="dim-card">
        <div class="label">{{ name }}</div>
        <div class="value">{{ "%.1f"|format(score * 100) }}%</div>
      </div>
      {% endfor %}
    </div>
  </div>

  <!-- Scenario details -->
  <div class="card">
    <h2>Scenario Results</h2>
    <table>
      <thead><tr><th>Scenario</th><th>Status</th><th>Assertions</th><th>Tags</th></tr></thead>
      <tbody>
      {% for s in scenarios %}
      <tr>
        <td>{{ s.name }}</td>
        <td><span class="badge {{ 'pass' if s.passed else 'fail' }}">{{ 'PASS' if s.passed else 'FAIL' }}</span></td>
        <td>{{ s.assertions_passed }}/{{ s.assertions_total }}</td>
        <td>{{ s.tags }}</td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>

  <!-- Noise matrix (if available) -->
  {% if noise_matrix %}
  <div class="card">
    <h2>Noise Robustness Matrix</h2>
    <table>
      <thead><tr><th>SNR (dB)</th><th>Intent</th><th>Entity</th><th>Tool Call</th></tr></thead>
      <tbody>
      {% for row in noise_matrix %}
      <tr>
        <td>{{ row.snr }}</td>
        <td>{{ "%.0f"|format(row.intent * 100) }}%</td>
        <td>{{ "%.0f"|format(row.entity * 100) }}%</td>
        <td>{{ "%.0f"|format(row.tool * 100) }}%</td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
</div>
</body>
</html>
"""


class HTMLReportGenerator:
    """Generate a self-contained HTML report from test results."""

    def __init__(self, title: str = "Voice Test Framework Report"):
        self.title = title

    def generate(
        self,
        all_results: list[TestResults],
        output_path: str | Path = "report.html",
        evaluation_reports: list[dict[str, Any]] | None = None,
    ) -> Path:
        try:
            import jinja2
        except ImportError:
            # Fall back to simple string formatting
            return self._generate_simple(all_results, output_path)

        template = jinja2.Template(_HTML_TEMPLATE)

        passed = sum(1 for r in all_results if r.passed)
        failed = len(all_results) - passed
        total = len(all_results)

        # Aggregate dimension scores
        dimensions: dict[str, float] = {}
        if evaluation_reports:
            for key in ("latency", "accuracy", "naturalness", "tool_use"):
                scores = [
                    r.get(key, {}).get("score", 0)
                    for r in evaluation_reports
                    if isinstance(r.get(key), dict)
                ]
                if scores:
                    dimensions[key] = sum(scores) / len(scores)

        scenarios = []
        for i, r in enumerate(all_results):
            a_total = len(r.assertions)
            a_passed = sum(1 for a in r.assertions if a.passed)
            scenarios.append({
                "name": r.metadata.get("scenario_name", f"Scenario {i + 1}"),
                "passed": r.passed,
                "assertions_passed": a_passed,
                "assertions_total": a_total,
                "tags": ", ".join(r.tags) if r.tags else "-",
            })

        html = template.render(
            title=self.title,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            total_scenarios=total,
            passed=passed,
            failed=failed,
            pass_rate=round(passed / total * 100, 1) if total else 0,
            dimensions=dimensions,
            scenarios=scenarios,
            noise_matrix=None,
        )

        output_path = Path(output_path)
        output_path.write_text(html, encoding="utf-8")
        return output_path

    def _generate_simple(
        self, all_results: list[TestResults], output_path: str | Path
    ) -> Path:
        """Minimal HTML when Jinja2 is unavailable."""
        passed = sum(1 for r in all_results if r.passed)
        total = len(all_results)
        html = (
            f"<html><body><h1>{self.title}</h1>"
            f"<p>{passed}/{total} scenarios passed</p></body></html>"
        )
        output_path = Path(output_path)
        output_path.write_text(html, encoding="utf-8")
        return output_path
