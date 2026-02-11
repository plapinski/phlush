# PHP Static Analysis Metrics Guide

Reference document for interpreting metrics from PHPMD and pdepend.

---

## Method-Level Metrics

### CCN — Cyclomatic Complexity (McCabe, 1976)

Counts the number of linearly independent paths through a method. Each `if`, `elseif`, `while`, `for`, `foreach`, `case`, `catch`, `&&`, `||`, `?:` adds one to the count.

**What it measures:** Decision complexity — how many paths exist through the code.

**Why it matters:** High CCN correlates strongly with defect density. Methods with CCN > 10 are statistically harder to test (each path needs at least one test case) and harder to reason about during code review.

**Academic basis:** McCabe, T.J. (1976). "A Complexity Measure." IEEE Transactions on Software Engineering, SE-2(4), 308-320.

### CCN2 — Extended Cyclomatic Complexity

Like CCN but counts each case in a switch individually and accounts for boolean sub-expressions. Typically CCN2 >= CCN.

**When to use over CCN:** Prefer CCN2 when evaluating methods with complex boolean conditions or large switch statements.

### NPath — Acyclic Execution Path Complexity (Nejmeh, 1988)

Counts the total number of acyclic execution paths through a method. Unlike CCN (which is additive), NPath is multiplicative — nested conditionals multiply rather than add.

**What it measures:** The number of unique paths through a method, considering nesting.

**Why it matters:** A method with moderate CCN can have enormous NPath if conditions are deeply nested. NPath > 200 means the method is effectively untestable — you cannot write enough test cases to cover all paths.

**Example:** Three nested if/else blocks: CCN = 4, NPath = 2 x 2 x 2 = 8. Add a 4th nested level: CCN = 5, NPath = 16.

### MI — Maintainability Index (Oman & Hagemeister, 1992)

Composite metric: `171 - 5.2 * ln(HV) - 0.23 * CCN - 16.2 * ln(LOC)`, normalized to 0-100 scale.

Components:
- **HV** (Halstead Volume): measures code vocabulary size and length
- **CCN**: cyclomatic complexity
- **LOC**: lines of code

**What it measures:** Overall maintainability on a 0-100 scale.

**Why it matters:** MI below 65 means the method is difficult to maintain. MI below 20 is nearly unmaintainable. When MI is low, identify which component is dragging it down:
- High Halstead Volume → too many distinct operators/operands (simplify expressions)
- High CCN → too many decision points (extract methods, guard clauses)
- High LOC → method too long (extract methods)

**Academic basis:** Oman, P. & Hagemeister, J. (1992). "Metrics for Assessing a Software System's Maintainability." Proc. IEEE International Conference on Software Maintenance.

### Method LOC — Lines of Code

Raw line count of a method body including blank lines and comments.

**What it measures:** Method size.

**Why it matters:** Long methods indicate multiple responsibilities packed into one unit. Methods under 20 lines are generally readable in one screen without scrolling.

### Parameter Count

Number of parameters a method accepts.

**What it measures:** Interface complexity.

**Why it matters:** Methods with many parameters are hard to call correctly, hard to test (combinatorial explosion), and often indicate the method does too much. Consider introducing a parameter object or breaking the method apart.

---

## Class-Level Metrics

### WMC — Weighted Methods per Class (Chidamber & Kemerer, 1994)

Sum of cyclomatic complexities of all methods in a class. If a class has 5 methods with CCN 3, 5, 8, 2, 1, then WMC = 19.

**What it measures:** Total complexity concentrated in one class.

**Why it matters:** High WMC means the class is doing a lot of complex work. It predicts maintenance effort and defect probability. Classes with WMC > 50 are almost always in need of decomposition.

### CBO — Coupling Between Objects (Chidamber & Kemerer, 1994)

Count of distinct classes that this class depends on (uses, references, calls). Includes constructor injections, method parameter types, return types, and internal instantiations.

**What it measures:** How many other classes this class is coupled to.

**Why it matters:** High CBO means a change in any of those coupled classes may require changes here. It makes the class harder to reuse and harder to test in isolation. CBO > 14 usually indicates a class that is trying to orchestrate too much.

### DIT — Depth of Inheritance Tree (Chidamber & Kemerer, 1994)

Number of ancestor classes (depth in the inheritance hierarchy). A class extending `Model` which extends `Eloquent` has DIT = 2.

**What it measures:** How deep in the inheritance chain a class sits.

**Why it matters:** Deep hierarchies increase cognitive load (you need to understand all parent behavior) and increase fragility (changes to parents cascade). DIT > 5 suggests replacing inheritance with composition.

### LCOM — Lack of Cohesion of Methods (Chidamber & Kemerer, 1994)

Measures how related the methods of a class are by examining which instance variables each method accesses. High LCOM means methods operate on disjoint subsets of fields.

**What it measures:** How focused a class is on a single responsibility.

**Why it matters:** High LCOM is a strong indicator that a class contains multiple responsibilities that should be separate classes. If method group A uses fields {x, y} and method group B uses fields {z, w} with no overlap, those are two classes masquerading as one.

### NOM — Number of Methods

Total method count in a class.

**What it measures:** Class interface size.

**Why it matters:** Classes with many methods may have too broad a public API. Combined with LCOM, high NOM confirms a class needs decomposition.

### Ca — Afferent Coupling

Number of classes that depend on this class (incoming dependencies).

**What it measures:** How many other classes would be affected if this class changes.

**Why it matters:** High Ca means the class is widely used — changes are risky. These classes should be stable and well-tested.

### Ce — Efferent Coupling

Number of classes this class depends on (outgoing dependencies). Similar to CBO.

### Instability — I = Ce / (Ca + Ce)

Ratio from 0 (maximally stable, many dependents) to 1 (maximally unstable, depends on many things).

**What it measures:** The class's susceptibility to change.

**Why it matters:** Stable classes (low I) should be abstract. Unstable classes (high I) should be concrete. This is the Stable Abstractions Principle.

---

## Metric Relationships — Compound Indicators

These combinations are more telling than individual metrics:

| Combination | Interpretation |
|---|---|
| High WMC + High LCOM | **God class** — multiple responsibilities with complex logic. Split into focused classes. |
| High CCN + Low MI | **Unmaintainable method** — complex and hard to work with. Extract submethods, add guard clauses. |
| High CBO + Low MI | **Fragile class** — tightly coupled and hard to maintain. Introduce interfaces, dependency inversion. |
| High NPath + Moderate CCN | **Deeply nested conditionals** — NPath multiplies while CCN adds. Flatten with early returns. |
| High WMC + Low NOM | **Few but complex methods** — each method is carrying too much weight. Decompose methods. |
| High CBO + High Ca | **Hub class** — many depend on it AND it depends on many. Reduce its outgoing dependencies. |
| Low LCOM + High NOM | **Cohesive but large** — well-focused but could benefit from extracting sub-concerns. |

---

## References

- McCabe, T.J. (1976). "A Complexity Measure." IEEE TSE, SE-2(4).
- Nejmeh, B.A. (1988). "NPATH: A Measure of Execution Path Complexity." CACM, 31(2).
- Oman, P. & Hagemeister, J. (1992). "Metrics for Assessing a Software System's Maintainability." Proc. IEEE ICSM.
- Chidamber, S.R. & Kemerer, C.F. (1994). "A Metrics Suite for Object Oriented Design." IEEE TSE, 20(6).
- Halstead, M.H. (1977). "Elements of Software Science." Elsevier.
