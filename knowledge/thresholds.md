# Severity Thresholds

Classification tables for mapping metric values to OK / WARN / CRITICAL severity.

These thresholds are used by `tools/analyze.py` to tag each metric in the report. The Haiku agent uses them to prioritize findings.

---

## Method-Level Thresholds

| Metric | OK | WARN | CRITICAL |
|---|---|---|---|
| CCN | 1-5 | 6-10 | >10 |
| NPath | 1-80 | 81-200 | >200 |
| MI | 85+ | 65-84 | <65 |
| Method LOC | 1-20 | 21-50 | >50 |
| Parameters | 0-3 | 4-5 | >5 |

### Reading the method table

- **CCN 1-5**: Straightforward method, easily testable. No action needed.
- **CCN 6-10**: Moderate complexity. Review for extract-method opportunities, but may be acceptable for orchestration methods.
- **CCN >10**: High complexity. Almost always benefits from decomposition. Each decision point is an additional thing to test and reason about.

- **NPath 1-80**: Manageable path count. Full path coverage is feasible.
- **NPath 81-200**: Significant path explosion. Consider whether all paths need to exist.
- **NPath >200**: Effectively untestable. Deep nesting is the usual cause — flatten with early returns and extracted methods.

- **MI 85+**: Highly maintainable code. Clean and easy to work with.
- **MI 65-84**: Acceptable but worth monitoring. May degrade further as the method grows.
- **MI <65**: Difficult to maintain. Investigate which MI component (Halstead, CCN, LOC) is dragging the score down.

---

## Class-Level Thresholds

| Metric | OK | WARN | CRITICAL |
|---|---|---|---|
| WMC | 1-20 | 21-50 | >50 |
| CBO | 0-8 | 9-14 | >14 |
| DIT | 0-3 | 4-5 | >5 |
| LCOM | 0-1 | 2-3 | >3 |
| NOM | 1-10 | 11-20 | >20 |
| Class LOC | 1-200 | 201-400 | >400 |

### Reading the class table

- **WMC 1-20**: Low total complexity. Class is focused and manageable.
- **WMC 21-50**: Moderate complexity. Check if methods can be extracted to helper classes.
- **WMC >50**: High complexity concentration. Strong candidate for Extract Class refactoring. Identify method groups by shared field access.

- **CBO 0-8**: Reasonable coupling. Class has a bounded set of collaborators.
- **CBO 9-14**: Elevated coupling. Review whether all dependencies are necessary. Consider facades or mediators.
- **CBO >14**: Excessive coupling. Class is likely an orchestrator trying to do too much. Apply Dependency Inversion.

- **DIT 0-3**: Acceptable inheritance depth. Common in framework-based code (Controller -> BaseController -> Framework).
- **DIT 4-5**: Getting deep. Check whether composition would be simpler.
- **DIT >5**: Too deep. Replace inheritance with delegation/composition.

- **LCOM 0-1**: Highly cohesive. Methods share state well — this is a focused class.
- **LCOM 2-3**: Some divergence among methods. Check if distinct method groups are forming.
- **LCOM >3**: Low cohesion. Methods operate on disjoint field subsets — likely multiple classes in disguise.

---

## Threshold Adjustments by Context

Not all code follows the same rules. Apply these adjustments when classifying severity:

### Test Files
- **Relax all thresholds by 50%** (e.g., CCN CRITICAL becomes >15 instead of >10)
- Test methods are inherently more verbose (arrange-act-assert)
- High NOM is expected (one test per behavior)
- LCOM is meaningless for test classes

### DTOs / Value Objects
- **Ignore NOM and LCOM** — DTOs have many getters by design
- **WMC should still be low** — DTOs shouldn't contain complex logic
- **CBO is usually 0-2** — DTOs should have minimal dependencies

### Controllers
- **Stricter LOC per method** — controller actions should be thin (< 15 lines)
- **CBO thresholds apply normally** — too many injected services = too much orchestration
- **WMC should be very low** — controllers delegate, they don't compute

### Service Classes
- **Standard thresholds apply**
- **Pay extra attention to CBO** — services that depend on too many other services need an orchestration layer or event-based decoupling

### Abstract / Base Classes
- **DIT is self-referential** — focus on the concrete classes that extend them
- **High NOM may be acceptable** — base classes sometimes provide shared utilities
- **Watch for Template Method abuse** — if abstract methods force complex implementations

### Migrations
- **Skip entirely** — migrations are write-once procedural code

### Config Files
- **Skip entirely** — configuration arrays are not object-oriented code

### Generated Code
- **Skip entirely** — IDE helpers, compiled assets, auto-generated files
