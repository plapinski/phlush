# Refactoring Catalog

Maps metric violations to concrete refactoring patterns. Use this when providing actionable suggestions for specific findings.

---

## High CCN (Cyclomatic Complexity > 10)

### Extract Method
Break the method into smaller named methods, each handling one concern.

**When:** The method has multiple blocks of logic separated by comments or blank lines.

**Approach:**
1. Identify logical sections within the method
2. Extract each section into a method with a descriptive name
3. The original method becomes a coordinator calling the extracted methods
4. Each extracted method should have a single level of abstraction

### Guard Clauses (Replace Nested Conditionals with Early Returns)
Convert nested if/else chains into flat guard clauses that return early.

**When:** The method has deeply nested conditionals where the "happy path" is buried inside multiple levels.

**Approach:**
1. Identify error/edge cases handled in outer conditionals
2. Invert each condition and return early
3. The main logic moves to the top level, reducing indentation

### Replace Conditional with Polymorphism
Replace type-checking conditionals with polymorphic dispatch.

**When:** A switch/if-else chain selects behavior based on a type field or class name, and this pattern repeats across methods.

**Approach:**
1. Identify the type discriminator
2. Create a class hierarchy or strategy interface
3. Move each conditional branch into an override/implementation
4. Replace the conditional with a polymorphic method call

---

## High NPath (> 200)

### Linearize Control Flow
Flatten deeply nested conditionals by inverting conditions and returning early.

**When:** NPath is high but CCN is moderate — indicating deep nesting rather than many branches.

**Approach:**
1. Map the nesting structure
2. Convert outer conditionals to guard clauses (early return)
3. Extract inner conditional blocks into separate methods
4. The goal: each method has at most 1-2 levels of nesting

### Decompose Conditional
Extract complex boolean expressions into named methods or variables.

**When:** Conditions themselves are complex (`if ($a && ($b || $c) && !$d)`).

**Approach:**
1. Extract the condition into a method: `if ($this->isEligibleForDiscount($order))`
2. Complex sub-expressions become helper methods
3. Each helper method is independently testable

---

## Low MI (Maintainability Index < 65)

MI is a composite metric. The fix depends on which component is dragging it down:

### High Halstead Volume (too many operators/operands)
The method has too much vocabulary — many distinct operations and variables.

**Approach:**
1. Extract complex expressions into named intermediate variables
2. Move calculation sub-steps into helper methods
3. Replace magic numbers/strings with named constants

### High CCN Component
Apply CCN refactoring patterns above.

### High LOC Component
The method is simply too long.

**Approach:**
1. Apply Extract Method to separate concerns
2. Check for copy-pasted blocks that can be unified
3. Move setup/teardown logic into dedicated methods

---

## High WMC (Weighted Methods per Class > 50)

### Extract Class
Split a class with too much complexity into focused collaborators.

**When:** The class has method groups that operate on different subsets of fields.

**Approach:**
1. List all instance fields
2. For each method, note which fields it accesses
3. Group methods by shared field access — each group is a candidate class
4. Extract groups into new classes
5. The original class delegates to the new classes

### Move Method
Move methods to the class whose data they primarily use.

**When:** Some methods exhibit Feature Envy — they access another object's data more than their own.

**Approach:**
1. Identify methods that reference external objects heavily
2. Move the method to the class that owns the data
3. If needed, pass the remaining dependencies as parameters

---

## High CBO (Coupling Between Objects > 14)

### Introduce Facade
Create a simplified interface that wraps a subset of the class's dependencies.

**When:** The class depends on many classes but some of those dependencies serve a single sub-concern.

**Approach:**
1. Group dependencies by the concern they serve
2. Create a facade class that wraps each group
3. The original class depends on fewer, coarser-grained collaborators

### Dependency Inversion
Depend on abstractions (interfaces) instead of concrete classes.

**When:** The class directly references implementation classes that could be swapped or mocked.

**Approach:**
1. Identify concrete dependencies that represent capabilities (not data)
2. Extract an interface for each
3. The class depends on the interface; concrete classes are injected

### Extract Mediator/Coordinator
Replace direct class-to-class communication with a mediator.

**When:** Multiple classes reference each other in a web pattern.

**Approach:**
1. Identify the communication pattern between coupled classes
2. Introduce a mediator that coordinates the interaction
3. Each class depends only on the mediator, not on each other

---

## High LCOM (Lack of Cohesion > 3)

### Extract Class (by field affinity)
When methods cluster around different fields, each cluster is a separate class.

**When:** LCOM is high and method-field analysis reveals disjoint groups.

**Approach:**
1. Draw a method-field access matrix
2. Identify connected components (groups of methods sharing fields)
3. Each component becomes a class
4. The original class becomes a facade or is removed

### Inline Class (if class is too thin after extraction)
If extraction leaves a class with only 1-2 trivial methods, inline it into its caller.

---

## High DIT (Depth of Inheritance > 5)

### Replace Inheritance with Delegation (Composition over Inheritance)
Convert deep inheritance chains into composition relationships.

**When:** The subclass only uses a fraction of the parent's behavior, or the hierarchy is confusing.

**Approach:**
1. Identify which parent behaviors the subclass actually uses
2. Create a collaborator object that provides those behaviors
3. Replace `extends Parent` with a field `private Parent $delegate`
4. Forward the needed methods to the delegate

### Collapse Hierarchy
Merge classes in the hierarchy that don't add meaningful behavior.

**When:** Middle classes in the hierarchy are nearly empty or just pass through to parents.

**Approach:**
1. Identify classes that add no or trivial behavior
2. Move their unique behavior (if any) to the parent or child
3. Remove the middle class

---

## High Parameter Count (> 5)

### Introduce Parameter Object
Group related parameters into a value object or DTO.

**When:** The same group of parameters appears together in multiple method signatures.

**Approach:**
1. Identify parameters that represent a single concept (e.g., date range = start + end)
2. Create a value object / DTO holding those parameters
3. Replace the parameter list with the object
4. Bonus: validation logic can move into the parameter object

### Preserve Whole Object
Pass the object from which parameters were extracted, instead of extracting individual fields.

**When:** A method receives 3+ fields that all come from the same source object.

**Approach:**
1. Identify the source object
2. Pass the whole object instead of its fields
3. The method extracts what it needs internally

---

## General Principles for Refactoring

1. **One refactoring at a time.** Apply a single pattern, verify tests pass, then consider the next.
2. **Tests first.** If the code lacks tests, add characterization tests before refactoring.
3. **Preserve behavior.** Refactoring changes structure, not behavior. If tests break, the refactoring introduced a bug.
4. **Name well.** Extracted methods and classes should have names that reveal intent, not implementation.
5. **Stop when good enough.** Not every WARN needs to become OK. Focus on CRITICAL findings and high-traffic code paths.
