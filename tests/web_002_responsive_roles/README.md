<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# WEB-002: Responsive USER and ADMIN experience

Primary type: Browser functional plus HITL visual  
Execution mode: Semi-automated  
Current feasibility: Blocked; frontend and auth UI are absent  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-WEB-MLR-602 | [SCRUM-564](https://pkamp.atlassian.net/browse/SCRUM-564) | SWE-WEB-MLR-602 - Responsive User/Admin Modes |
| SWE-WEB-LLR-606 | [SCRUM-580](https://pkamp.atlassian.net/browse/SCRUM-580) | SWE-WEB-LLR-606 - Responsive Layout |
| SWE-WEB-LLR-607 | [SCRUM-581](https://pkamp.atlassian.net/browse/SCRUM-581) | SWE-WEB-LLR-607 - Role Model |
| SWE-WEB-LLR-608 | [SCRUM-582](https://pkamp.atlassian.net/browse/SCRUM-582) | SWE-WEB-LLR-608 - User Permissions |
| SWE-WEB-LLR-609 | [SCRUM-583](https://pkamp.atlassian.net/browse/SCRUM-583) | SWE-WEB-LLR-609 - Admin Permissions |

## Purpose and usefulness

Role workflows and layout are coupled user experiences; exercising both accounts across fixed viewports is more useful than isolated CSS property checks.

## Profiles and qualification credit

- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, pr1-console, browser, scripted-source, implementation:WEB-002:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Create USER and ADMIN accounts; run the production UI at 360x800, 768x1024, and 1440x900 viewports with representative long values/status text.

## Detailed repeatable procedure

1) Sign in as USER and visit graph/current, settings, and control routes directly and through navigation. 2) Verify read-only views work and mutations are unavailable/denied. 3) Sign in as ADMIN and verify control/settings are usable. 4) At each viewport detect horizontal document overflow and clipped/overlapping controls. 5) Capture screenshots of graph, current cards, settings, and control pages. 6) Use keyboard navigation and zoom to 200 percent as a practical accessibility screen.

## PASS criteria

At all three viewports there is no page-level horizontal overflow, unreadable overlap, or inaccessible required control. USER can view current/graph but cannot mutate controls/settings/accounts; ADMIN can access required mutation functions. Two reviewers accept representative screenshots.

## Independent criteria source

Jira says common phone and desktop widths but gives none; 360, 768, and 1440 pixels are documented representative test widths and can be updated with supported-device policy.

## Test type and automation rationale

Browser checks automate permissions/overflow; visual usability retains HITL review.

## Required instrumentation and observability

Implement responsive UI/auth, route guards, stable selectors, viewport matrix, screenshot baselines, overflow detector, and accessibility smoke checks.

## Evidence retained

Screenshots, DOM/overflow results, role navigation/mutation transcript, reviewer approval.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
