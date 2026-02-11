# Analysis Workflow

Step-by-step workflow with adaptive decision tree. Follow this exactly.

---

## Step 1: Pre-flight

Check Docker availability:

```bash
docker info > /dev/null 2>&1
```

If Docker is not running, tell the user to start Docker Desktop and stop.

## Step 2: First Run

Execute the analysis tool with the parsed arguments from SKILL.md:

```bash
$(command -v python3 || command -v python) .claude/skills/phlush/tools/analyze.py [flags]
```

Capture the full output. This is your primary data source.

**Exit code handling:**
- Exit 0: success, proceed to analysis
- Exit 1: infrastructure error — report the error and stop
- Exit 2: no PHP files found — report "no PHP files to analyze" and stop
- Exit 3: tool error — report what failed and stop

## Step 3: Adaptive Decision

Based on the report output, decide your next action:

| Output volume | Action |
|---|---|
| >50 PHPMD violations, mostly INFO priority | Re-run with `--focus-critical` flag added. Tell the user you're filtering noise. |
| >50 PHPMD violations, mostly CRITICAL/WARN | Do NOT re-run. Analyze the top 5 most severe findings. |
| 5-50 PHPMD violations | Good volume. Proceed to analysis. |
| <5 PHPMD violations | Code is relatively clean. Note this. Check pdepend for structural concerns. |
| pdepend all metrics OK | Skip pdepend discussion entirely. Focus on PHPMD. |
| PHPMD clean, pdepend has WARN/CRITICAL | Focus entirely on structural metrics. Load `knowledge/metrics-guide.md`. |
| Both tools clean | Report the code is in good shape. Optionally suggest running `--all` for broader coverage. |

**Key rule:** Only re-run the tool once. If the second run is still noisy, work with what you have.

## Step 4: Analysis

For each finding you choose to highlight (top 3-5):

1. **Read the report data** — identify the specific metric, value, file, and line/class/method
2. **Load knowledge on-demand:**
   - If you need to explain a metric, read `knowledge/metrics-guide.md`
   - If you need to verify a threshold, read `knowledge/thresholds.md`
   - If you need to suggest a refactoring, read `knowledge/refactoring-catalog.md`
3. **Identify compound indicators** — check for metric combinations that tell a bigger story:
   - High WMC + High LCOM = God class
   - High CCN + Low MI = unmaintainable method
   - High CBO + High WMC = fragile orchestrator
   - High NPath + Moderate CCN = deeply nested conditionals

## Step 5: Output

Structure your response as follows:

### Per-finding format

For each of the top 3-5 findings:

```
[SEVERITY] file:location — Metric/Rule

What: Plain-language description of the issue.
Why it matters: Concrete consequence (harder to test, higher defect risk, etc.).
Fix direction: Specific refactoring approach, referencing the code context.
```

### Overall assessment

After individual findings, provide a 2-3 sentence overall assessment:
- Is this code in good shape or does it need focused attention?
- What is the single most impactful improvement the developer could make?
- If code is clean, acknowledge it and note any positive patterns.

### What NOT to include

- Do not list every single violation — only the most impactful ones
- Do not explain what PHPMD or pdepend are — the user knows
- Do not repeat raw numbers without interpretation
- Do not hedge excessively — be direct about what needs attention
- Do not suggest running additional tools — this skill covers what's needed
