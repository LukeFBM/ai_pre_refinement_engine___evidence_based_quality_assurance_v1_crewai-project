# Changes: Anti-Hallucination & Repo Scope Lock

## Problem

The previous run failed because:

1. **Repository Scout hallucinated** — It claimed microservices architecture, Express framework, MariaDB, event-driven patterns, payment gateway integration, recent commits and MRs — all without reading a single file.
2. **Root cause**: gpt-4o-mini at temperature=1.0 (maximum randomness + weakest model) for the most critical evidence-gathering agent.
3. **No verification tools** — Downstream agents (Synthesis, Complexity, Product Optimizer) had zero tools, so they couldn't spot-check claims.
4. **Quality Gate caught it** but only after the entire pipeline had already consumed fabricated data, resulting in a full VETO.
5. **Placeholder input** — `feature_idea` was `"sample_value"` with no real feature description.
6. **No repo scope lock** — Agents could theoretically analyze any repo in the group instead of the 6 target repos.

## What Changed

### 1. Temperature Reduction (all 7 agents) — `crew.py`

| Agent | Before | After | Why |
|---|---|---|---|
| Planner & Orchestrator | 1.0 | **0.2** | Strategy planning needs consistency, not randomness |
| Repository Scout | 1.0 | **0.1** | Evidence gathering must be factual and deterministic |
| Synthesis Tech Lead | 1.0 | **0.3** | Needs some creativity but must stay grounded in evidence |
| Product Optimizer | 1.0 | **0.4** | Variants benefit from creativity but within evidence bounds |
| Quality Gate Critic | 1.0 | **0.0** | Validation must be completely deterministic |
| Cache Intelligence Manager | 1.0 | **0.2** | Caching strategy needs precision |
| Complexity Assessment Specialist | 1.0 | **0.2** | Scoring must be consistent and evidence-based |

**Why this matters**: Temperature=1.0 means maximum randomness. For an agent whose job is to read files and report what's in them, high temperature literally encourages the model to "be creative" — i.e., make things up. Temperature=0.1 forces the model to stay close to the most likely (factual) response.

### 2. Model Upgrade for Repository Scout — `crew.py`

| Agent | Before | After |
|---|---|---|
| Repository Scout | `openai/gpt-4o-mini` | `openai/gpt-4.1` |

**Why this matters**: gpt-4o-mini is a small, cheap model optimized for simple tasks. It struggles with complex multi-step tool-use instructions (like "read this file, then analyze it, then cite it"). gpt-4.1 is significantly more capable at following instructions and using tools correctly.

### 3. Verification Tools for Downstream Agents — `crew.py`

Previously, only the Repository Scout had tools. All other agents had `tools=[]` and could only work with text passed to them — they couldn't verify anything.

| Agent | Before | After |
|---|---|---|
| Synthesis Tech Lead | `tools=[]` | `tools=[GitLabFileReadTool, GitLabGetFileTool]` |
| Product Optimizer | `tools=[]` | `tools=[GitLabFileReadTool]` |
| Quality Gate Critic | `tools=[]` | `tools=[GitLabFileReadTool, GitLabGetFileTool]` |
| Complexity Assessment Specialist | `tools=[]` | `tools=[GitLabFileReadTool]` |
| Cache Intelligence Manager | `tools=[]` | `tools=[]` (unchanged — doesn't need file access) |

**Why this matters**: Now the Quality Gate Critic can actually **spot-check citations** by reading the files itself. If the Repository Scout claims a file contains Express routes, the Critic can read that file and verify. Same for the Synthesis Tech Lead — if it doubts an upstream claim, it can verify directly.

### 4. Anti-Hallucination Rules in Agent Backstories — `agents.yaml`

Each agent now has explicit rules appended to its backstory:

**Repository Scout** — 7 mandatory rules including:
- NEVER state a file exists unless a file-reading tool returned success
- NEVER describe code content unless you read the actual file
- If tool returns 404, report NOT_FOUND — never guess
- Every finding must cite exact tool call and file path: `repo@branch:file_path`
- NEVER invent commit dates, MR numbers, or issue IDs
- SCOPE: Only analyze the 6 target repositories

**Synthesis Tech Lead** — 5 strict rules including:
- Every claim must cite evidence using `repo@ref:path` format
- Missing evidence = mark as UNKNOWN with confidence LOW
- Clearly separate EVIDENCE / HYPOTHESIS / UNKNOWN
- Use file-reading tools to verify doubtful upstream claims
- Numeric thresholds without code evidence = mark as ASSUMPTION

**Quality Gate Critic** — 5 enforcement rules including:
- SPOT-CHECK at least 3 file citations using file-reading tools
- Cited file doesn't exist or has different content = immediate VETO
- HIGH confidence requires 3+ evidence citations
- Report citation_coverage as percentage
- FAIL for invented file paths, fabricated content, unstated assumptions

**Product Optimizer** — 4 rules including:
- Base variants only on upstream evidence — never invent capabilities
- Any framework/library referenced must appear in evidence
- Verify uncertain claims before building variants around them

**Complexity Assessment Specialist** — 4 rules including:
- Score UNKNOWN for dimensions lacking evidence
- Every score justification must cite upstream evidence
- Verify uncertain claims with file-reading tool before scoring
- Unverified upstream evidence = BLOCKED dimension

### 5. Repo Scope Lock to 6 Target Repositories — `tasks.yaml`

The following tasks now include a **SCOPE LOCK** directive:

| Task | Scope Lock Added |
|---|---|
| `input_normalization_and_gitlab_scope_validation` | Hardcoded 6 target repos with discovery instructions |
| `repository_inventory_and_candidate_selection` | "Only select from these 6 repositories... Ignore ALL other projects" |
| `two_pass_evidence_retrieval` | "Only analyze these 6 repositories... Do NOT access any other" |
| `mr_issue_similarity_mining` | "Only mine MRs/issues from these 6 repositories" |
| `execute_two_pass_analysis_with_intelligent_stopping` | Scope lock + anti-hallucination directive |
| `bootstrap_repository_system_map` | Scope lock + anti-hallucination directive |

**Target repositories (all under `radical-app` group):**
1. APIv3
2. Admin catalog
3. Next
4. Pages-Next
5. Front end monorepo
6. booking

The discovery task now instructs the agent to:
1. Call `GitLabListGroupProjectsTool` with `group_path="radical-app"`
2. Match results against the 6 target names (case-insensitive, partial match)
3. Output ONLY the matched repos
4. Report any MISSING repos

### 6. Input Validation — `main.py`

- **Rejects placeholder inputs**: If `feature_idea` is `"sample_value"` or empty, the crew refuses to start and prints an error with usage instructions.
- **CLI argument support**: You can now pass the feature idea directly: `python main.py run "your feature description"`
- **Removed `item_id`**: This was never referenced by any task or agent.

---

## How to Test

### Quick Verification Checklist

Run the crew and check these things in the verbose output:

#### 1. Input validation works
```bash
# This should FAIL with a clear error:
python main.py run

# This should FAIL with a clear error:
python main.py run "sample_value"

# This should START the crew:
python main.py run "Add neighborhood-based rating system to booking search results"
```

#### 2. Repo discovery finds the 6 target repos
In the verbose output for the first tasks, look for:
- A call to `GitLabListGroupProjectsTool` with `group_path="radical-app"`
- The output should list real project IDs (not round numbers like 10000)
- Only the 6 target repos should appear in the candidate list

**What to check:**
```
PASS: You see actual GitLab API calls returning real project data
FAIL: The agent lists repos without calling any tool, or lists repos outside the 6 targets
```

#### 3. Repository Scout actually reads files
In the verbose output for evidence retrieval tasks, look for:
- Multiple calls to `GitLab File Reader` or `GitLab Get File` tools
- Each evidence claim followed by a citation like `radical-app/apiv3@main:package.json`
- If a file is not found, it should say "NOT_FOUND" (not guess the contents)

**What to check:**
```
PASS: You see tool calls like "GitLab File Reader" with real file content in responses
FAIL: The agent describes file contents without any tool calls preceding the description
```

#### 4. All 6 repos are accessible and readable
For each of the 6 repos, confirm in the output that:
- The repo was discovered with a valid project_id
- At least one file was successfully read from each repo
- The tree listing returned actual files/directories

**What to check per repo:**
```
APIv3:              project_id found? [ ] | Files read? [ ] | Tree listed? [ ]
Admin catalog:      project_id found? [ ] | Files read? [ ] | Tree listed? [ ]
Next:               project_id found? [ ] | Files read? [ ] | Tree listed? [ ]
Pages-Next:         project_id found? [ ] | Files read? [ ] | Tree listed? [ ]
Front end monorepo: project_id found? [ ] | Files read? [ ] | Tree listed? [ ]
booking:            project_id found? [ ] | Files read? [ ] | Tree listed? [ ]
```

If any repo fails, check:
- Is the GitLab token (`GITLAB_API_KEY` / `GITLAB_AUTH_KEY` in `.env`) valid?
- Does the token have `read_repository` permission for that repo?
- Is the repo name slightly different in GitLab? (The matching is case-insensitive and partial)

#### 5. Quality Gate Critic spot-checks citations
In the quality gate tasks, look for:
- The Critic calling `GitLab File Reader` to verify cited files
- A `citation_coverage` percentage in the output
- If any spot-check fails: a VETO with specific details about which citation was fabricated

**What to check:**
```
PASS: Critic shows "Spot-checked 3 citations: all verified" (or similar)
FAIL: Critic reports citations without having called any verification tools
```

#### 6. No hallucinated content
Review the final report for:
- Every technical claim has a `repo@ref:path` citation
- No invented frameworks, databases, or architecture claims without citations
- Unknown dimensions scored as UNKNOWN with LOW confidence
- Numeric thresholds marked as ASSUMPTION unless found in code

### Common Issues & Troubleshooting

| Issue | Likely Cause | Fix |
|---|---|---|
| "GITLAB_API_KEY not set" | `.env` not loaded | Ensure `.env` contains valid `GITLAB_API_KEY` and `GITLAB_AUTH_KEY` |
| Repos not found | Group path wrong or token lacks access | Verify `radical-app` is correct group path; check token permissions |
| Some repos missing | Name mismatch | The exact GitLab slug may differ from the display name; check the group listing output |
| Scout still hallucinating | Temperature not applied | Verify `crew.py` has `temperature=0.1` for repository_scout |
| Quality Gate not spot-checking | Tools not assigned | Verify `crew.py` has `tools=[GitLabFileReadTool(), GitLabGetFileTool()]` for quality_gate_critic |
| "sample_value" error | Old run command | Use: `python main.py run "your actual feature description"` |

### Running via CrewAI CLI

If you use the CrewAI CLI instead of `main.py` directly:
```bash
# Using uv:
uv run run_crew "Add neighborhood-based rating system to booking search results"

# Or if crewai CLI is installed:
crewai run "Add neighborhood-based rating system to booking search results"
```

---

## Files Modified

| File | Changes |
|---|---|
| `src/.../crew.py` | Temperature reduction (all 7 agents), model upgrade (repository_scout → gpt-4.1), added verification tools to 4 agents |
| `src/.../config/agents.yaml` | Anti-hallucination rules appended to all 7 agent backstories |
| `src/.../config/tasks.yaml` | Scope lock added to 6 evidence-gathering tasks, anti-hallucination directives added |
| `src/.../main.py` | Input validation (rejects placeholders), CLI argument support, removed unused `item_id` |
