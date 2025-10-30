Instructions

CRITICAL RULE #1: NEVER CLAIM SUCCESS WITHOUT VERIFIED TESTING

Absolute Requirements Before Claiming Success
	1.	NEVER use words like "successfully", "working", "complete", or "functional" unless code has been:
	◦	Actually executed/run
	◦	Produced expected output
	◦	Completed without errors
	◦	Verified through debug output or test results

Testing is MANDATORY
	•	Code that hasn't been run is UNTESTED
	•	Code that produces errors is BROKEN
	•	Code that runs but hasn't been verified is UNVERIFIED
	•	Only code that runs without errors AND produces expected results is WORKING

---

CRITICAL RULE #2: TEST IMPLEMENTATIONS USING UNIT AND INTEGRATION TESTING

Testing is Required for Every Implementation
	•	Every feature or code change must be tested before it can be considered verified.
	•	Testing can be automated or manual, but either way, validation is mandatory.

Automated Testing Guidelines
	1.	Choose the Right Framework
	◦	Web & Interactive Applications: Playwright, Cypress, Selenium
	◦	APIs & Backend Services: Jest, Mocha/Chai, Pytest, JUnit
	◦	Data Pipelines or Scripts: Pytest, unittest, or custom validation scripts
	2.	Set Up Automated Tests
	◦	Write unit tests for individual functions or modules.
	◦	Include integration tests that simulate complete workflows.
	◦	Run tests locally or in a CI/CD pipeline.
	3.	Verify Test Results
	◦	Ensure all tests pass without errors.
	◦	Review logs for warnings or unexpected outcomes.

Manual Testing Guidelines
	1.	Define Clear Test Steps
	◦	Step 1: Launch the environment or service where the code runs.
	◦	Step 2: Execute the feature/module with sample inputs.
	◦	Step 3: Observe outputs and behavior.
	2.	Know What to Expect
	◦	Determine expected results before testing.
	◦	Test both normal and edge cases.
	3.	Collect and Report Findings
	◦	Document errors, warnings, or mismatched behaviors.
	◦	Include logs, screenshots, and step-by-step notes.
	◦	Summarize actual results versus expected results.

Recommendation for Listing Verified Features
	•	Maintain a Testing Checklist or Verification List for all implementations.
	•	Each feature should include:
	1.	Feature name or module
	2.	Date of testing
	3.	Type of tests conducted (unit, integration, manual)
	4.	Test results summary
	5.	Verification status (e.g., VERIFIED, NEEDS FIXES)
	•	This ensures transparency, traceability, and easy auditing of tested work.

Final Verification
	•	Only after all tests pass and results match expectations can the implementation be considered working.
	•	Any deviation requires further debugging and re-testing.

