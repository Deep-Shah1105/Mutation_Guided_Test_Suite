# Synopsis

The Mutation-Guided Test Suite Generator is a multi-agent system that produces pytest unit tests for a supplied Python function and evaluates those tests by deliberately introducing program mutations. Instead of treating generated tests as successful merely because they run, the system checks whether they detect altered behavior. Surviving mutants are examined by a Mutation Analyst and, when classified as genuine test gaps, are returned to an Adversary agent so the next test-writing round targets the missed behavior.
