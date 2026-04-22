---
name: paper-analyzer
description: Analyze deep learning papers or code repositories and generate reproduction-ready documentation
version: 1.0.0
---

# Paper Analyzer Skill

Analyze deep learning papers (arXiv) or code repositories and generate detailed reproduction documents.

## Usage

```
/paper-analyzer <input> <output_dir> [options]
```

### Paper Mode
```
/paper-analyzer https://arxiv.org/abs/2301.00001 ./output/
/paper-analyzer 2301.00001 ./output/
```

### Code-Only Mode
```
/paper-analyzer https://github.com/xxx/yyy ./output/ --mode code
```

## Parameters

| Parameter | Description |
|-----------|-------------|
| `input` | arXiv link/ID or GitHub URL |
| `output_dir` | Output directory path |
| `--mode <paper\|code\|auto>` | Analysis mode (default: auto-detect) |
| `--deep` | Enable deep analysis (default: enabled) |
| `--no-agent` | Disable automatic subAgent research |
| `--lang <zh\|en>` | Output language |

## Language Convention

- **Agent internal communication**: English
- **User communication**: Chinese

## Two Modes

### Mode 1: Paper Analysis
```
Input: arXiv link/ID
Process: Download PDF → Analyze with subAgents → Cross-validate → Write understanding doc → Ask user
Output: Comprehensive paper understanding with reproduction guidance
```

### Mode 2: Code-Only Analysis
```
Input: GitHub URL
Process: Clone repo → Analyze code structure → Generate modules → Test with subAgent → Ask user
Output: Code analysis ready for integration
```

## Two-Phase Flow (Both Modes)

### Phase 1: Analysis
```
MainAgent processes input
    ↓
Discover image → Image Analyzer
    ↓
Discover formula → Formula Analyzer
    ↓
Discover code → Code Analyzer
    ↓
Cross-validation ← All analyzers corroborate
    ↓
Write Understanding Document
    ↓
Ask user for confirmation
```

### Phase 2: Reproduction (after user confirmation)
```
Create reproduction plan
    ↓
Implement modules (smallest first)
    ↓
Debug SubAgent tests each module (TDD cycle)
    ↓
All tests pass → Generate README.md
    ↓
Task complete
```

## Planning Files (planning-with-files)

MainAgent maintains real-time documents:

- `{output_dir}/task_plan.md` - Phase tracking
- `{output_dir}/findings.md` - Research discoveries
- `{output_dir}/progress.md` - Session log

**Critical Rules:**
1. Create plan files BEFORE any complex task
2. After every 2 operations, IMMEDIATELY save key findings
3. Read plan file before major decisions
4. After completing any phase, update status and log errors
5. Log ALL errors

## SubAgents

### Image Analyzer
- **Handles**: Architecture diagrams, flowcharts, experiment figures, tables, pseudocode
- **Output**: `{output_dir}/images/{image_id}/`
- **JSON**: modules, variables, data_flow

### Formula Analyzer
- **Handles**: Core formulas, custom functions, cross-formula linkage
- **Output**: `{output_dir}/formulas/{formula_id}/`
- **JSON**: variables, functions, operations, rigor assessment

### Code Analyzer
- **Handles**: Open source code analysis
- **Output**: `{output_dir}/code/`
- **Focus**: architecture | training | data_augmentation | feature_engineering

### Debug SubAgent (TDD)
- **Handles**: Test-driven development for reproduction
- **Follows**: Red-Green-Refactor cycle
- **Output**: Test logs in `{output_dir}/reproduction/log/`

## Output Structure

```
{output_dir}/
├── task_plan.md
├── findings.md
├── progress.md
├── UNDERSTANDING.md          # Main understanding document
├── images/{image_id}/
│   ├── report.md
│   ├── summary.md
│   └── analysis.json
├── formulas/{formula_id}/
│   ├── report.md
│   ├── summary.md
│   └── analysis.json
├── code/
│   ├── report.md
│   ├── summary.md
│   └── analysis.json
└── reproduction/            # Created after user confirmation
    ├── plan.md
    ├── README.md
    ├── config.py
    ├── model/
    ├── data/
    ├── loss/
    └── log/
```

## Key Principles

1. **planning-with-files**: Write important info to disk immediately
2. **TDD for reproduction**: Debug SubAgent follows Red-Green-Refactor
3. **Cross-validation**: All analyzers corroborate each other
4. **Minimal modules first**: Reproduction starts from smallest dependencies
5. **All tests pass**: Only complete after full integration test passes
6. **Information insufficient**: SubAgent must ask MainAgent, never guess
7. **Language**: Agent uses English internally, Chinese with users

---

For detailed specifications, see `prompt.md`.
