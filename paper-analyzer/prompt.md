# Paper Analyzer - Detailed Specifications

This document contains the complete specifications for the Paper Analyzer skill.

---

# Part 1: Input Handling

## Entry Point Script

`scripts/analyze.py` handles input parsing, PDF download, text extraction, and image extraction:

```
python scripts/analyze.py <input> <output_dir> [options]

Options:
  --mode <paper|code|auto>  Analysis mode (default: auto)
  --deep                     Deep analysis (default: on)
  --no-agent                 Disable automatic subAgent
  --lang <zh|en>            Output language
```

### Mode Detection
- `paper`: arXiv link/ID → download PDF + extract text/images → analyze
- `code`: GitHub URL → clone → analyze
- `auto`: Auto-detect based on input (default)

### Output Path Convention
- Paper mode creates: `{output_dir}/{arxiv-id}/`
- PDF: `{output_dir}/{arxiv-id}/{arxiv-id}.pdf`
- Extracted text: `{output_dir}/{arxiv-id}/{arxiv-id}.txt`
- Full-page images: `{output_dir}/{arxiv-id}/full_pages/` (150 DPI, for layout analysis)
- Cropped images: `{output_dir}/{arxiv-id}/crops/` (300 DPI, for detailed analysis)
- PDF structure: `{output_dir}/{arxiv-id}/pdf_structure.json`
- Manifests: `page_manifest.txt`, `paper_info.txt`

### Two-Stage Image Extraction (MANDATORY Workflow)
```
Stage 1: Full-page extraction (DONE BY SCRIPT)
- Script extracts full pages at 150 DPI to full_pages/page_N.png
- Script extracts PDF structure to pdf_structure.json (figure captions, table captions)
- Script creates page_manifest.txt listing all pages

Stage 2: Vision-based Figure Detection (DONE BY AGENT)
For each page with figures:
  1. Read full_pages/page_N.png
  2. Send to vision model to identify figure/table bounding boxes
  3. Vision model returns: {page: N, boxes: [{type: "figure", x0, y0, x1, y1, caption: "..."}]}
  4. Use --crop command to extract high-res crops at 300 DPI
  5. Save cropped images to crops/ directory

IMPORTANT: Do NOT analyze full-page images directly. Always crop first for high-res detail.
```

### Image Cropping Usage
```bash
# Crop a region from page 5 at 300 DPI
python scripts/analyze.py --crop --page 5 --bbox "100,200,400,500" ./output-dir

# Coordinates are in PDF points (72 points = 1 inch, origin at bottom-left)
# Example: crop from x=100, y=200 to x=400, y=500 points
```

---

# Part 2: Two-Phase Flow

## Phase 1: Analysis

```
MainAgent receives input
    ↓
[Paper Mode] Download PDF
[Code Mode] Clone repository
    ↓
MainAgent discovers entities while processing:
    ↓
Discover image → Image Analyzer
Discover formula → Formula Analyzer
Discover code → Code Analyzer
    ↓
Cross-validation ← All analyzers corroborate each other
    ↓
Write UNDERSTANDING.md
    ↓
Ask user for confirmation
```

### What to Analyze

**Paper Mode:**
- Focus on Method and Experiment sections
- Scan ALL figures, tables, formulas (DO NOT SKIP ANY)
- Extract architecture, loss functions, training details
- Read the extracted text from `{arxiv-id}.txt` for full paper content

**CRITICAL: Extract ALL Images and Formulas (Two-Stage)**
- Stage 1: Read `page_manifest.txt` and `paper_info.txt` to understand page structure
- Stage 2: For each page with figures/tables:
  1. Send full-page image (from `full_pages/`) to vision model
  2. Vision model returns bounding boxes for figures/tables
  3. Call `analyze.py --crop` to extract high-res crops at 300 DPI
  4. Analyze each cropped image individually

- Write a `processing_manifest.txt` file listing every entity to process:
  ```
  TOTAL_PAGES: N
  PAGE_1: full_pages/page_1.png
    FIGURES: [box1, box2]
    TABLES: [box3]
  ...
  TOTAL_FORMULAS: M
  FORMULA_1: eq_1 (page X)
  FORMULA_2: eq_2 (page Y)
  ...
  ```
- Track progress in `progress_manifest.txt`:
  ```
  PROCESSED_PAGES: X/N
  PROCESSED_FIGURES: Y/M figures
  PROCESSED_TABLES: Z/K tables
  ```
- DO NOT skip any entity - every figure, table, and formula must be analyzed
- For formulas in PDF: search for LaTeX patterns `$, $$, \( \)` in the text file, or infer from context

**Code Mode:**
- Analyze project structure
- Focus on core modules (model/training/data)
- Map to paper concepts if applicable

## Phase 2: Reproduction (after user confirmation)

```
Create reproduction plan (plan.md)
    ↓
Implement modules (smallest dependencies first)
    ↓
Debug SubAgent tests each module (TDD cycle)
    ↓
All tests pass → Generate README.md
    ↓
Task complete
```

---

# Part 3: Planning Files Pattern

## planning-with-files

MainAgent MUST maintain these files in real-time:

### task_plan.md
```markdown
# Task Plan: {task_name}

## Goal
[One sentence describing end state]

## Current Phase
Phase X

## Phases

### Phase 1: Analysis
- [ ] Step 1
- [ ] Step 2
- **Status:** in_progress

### Phase 2: Reproduction
- [ ] Step 1
- **Status:** pending

## Key Decisions
| Decision | Rationale |
|----------|-----------|

## Issues
| Issue | Resolution |
|-------|------------|
```

### findings.md
```markdown
# Findings & Decisions

## Requirements
-

## Research Findings
-

## Technical Decisions
| Decision | Rationale |
|----------|-----------|

## Cross-Validation Results
| Entity A | Entity B | Consistent? |
|----------|----------|--------------|

## Issues Encountered
| Issue | Resolution |
|-------|------------|
```

### progress.md
```markdown
# Progress Log

## Session: {date}

### Phase 1: Analysis
- **Status:** in_progress
- **Started:** {timestamp}

Actions taken:
-

Files created/modified:
-

### SubAgent Interactions
| Time | SubAgent | Task | Result |
|------|----------|------|--------|

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase X |
| Where am I going? | Remaining phases |
| What's the goal? | [goal] |
| What have I learned? | See findings.md |
| What have I done? | See above |
```

---

# Part 4: SubAgent Specifications

## 4.1 Image Analyzer

### Invocation
- When MainAgent has high-res cropped images from crops/ directory
- When user explicitly requests

### CRITICAL: Analyze CROPPED Images Only
- Full-page images (full_pages/) are for LAYOUT ANALYSIS ONLY
- Do NOT analyze full_pages/ images directly for figure content
- Only analyze images in crops/ directory
- Each crop should be ONE figure, table, or pseudocode
- Use vision model to analyze the cropped high-res image

### Input
```
- High-res cropped image from crops/ directory
- Image context: caption text, page number
```

### Output Directory Structure
```
{output_dir}/crops/{image_id}/
├── report.md      # Detailed analysis
├── summary.md     # For MainAgent
└── analysis.json  # Structured data
```

### Image Types & Analysis

**A. Architecture/Pipeline (Flowchart)**
```json
{
  "image_id": "fig_1",
  "image_type": "architecture",
  "modules": [
    {
      "id": "mod_1",
      "name": "ModuleName",
      "inputs": [{"source": "mod_x", "tensor": "name", "shape": "HxWxC"}],
      "outputs": [{"target": "mod_y", "tensor": "name", "shape": "HxWxC"}],
      "internals": ["sub1", "sub2"],
      "learnable": true,
      "init_method": "xavier|normal|pretrained",
      "pretrained": true,
      "finetune": false,
      "frozen": true,
      "operation_type": "conv|linear|attention|norm|activation|...",
      "parent_modules": ["mod_parent"],
      "child_modules": ["mod_child"]
    }
  ],
  "variables": [
    {
      "id": "var_1",
      "name": "tensor_name",
      "shape": "HxWxC",
      "from_module": "mod_x",
      "to_modules": ["mod_y"],
      "description": "..."
    }
  ],
  "data_flow": [
    {
      "id": "flow_1",
      "from_module": "mod_x",
      "to_module": "mod_y",
      "through_tensor": "tensor_name",
      "direction": "forward|backward",
      "description": "..."
    }
  ]
}
```

**B. Experiment Results**
```json
{
  "image_id": "fig_5",
  "image_type": "line|bar|heatmap|scatter|box|roc",
  "basic_info": {
    "x_axis": {"name": "...", "unit": "...", "range": [min, max]},
    "y_axis": {"name": "...", "unit": "...", "range": [min, max]}
  },
  "data_series": [
    {
      "name": "...",
      "data_points": [[x1, y1], [x2, y2]],
      "trend": "rising|falling|...|..."
    }
  ],
  "author_claim": "...",
  "key_findings": ["..."]
}
```

**C. Table**
```json
{
  "image_id": "table_1",
  "image_type": "table",
  "table_type": "comparison|results|ablation|data",
  "key_values": [
    {"row": 2, "col": 3, "value": "95.6%", "significance": "best|worst|..."}
  ],
  "author_claim": "..."
}
```

**D. Pseudocode**
```json
{
  "image_id": "algo_1",
  "image_type": "pseudocode",
  "basic_info": {
    "title": "...",
    "input": [{"name": "x", "shape": "HxWxC"}],
    "output": [{"name": "y", "shape": "NxC"}],
    "time_complexity": "O(n)",
    "space_complexity": "O(n)"
  },
  "steps": [
    {
      "step_id": 1,
      "code": "y = W @ x + b",
      "operation": "linear transformation",
      "variables_read": ["x", "W", "b"],
      "variables_written": ["y"],
      "corresponds_to_formula": "eq_3",
      "corresponds_to_module": "mod_1"
    }
  ],
  "correspondence": {
    "modules": [{"pseudocode": "step 1", "module": "mod_1"}],
    "formulas": [{"pseudocode": "step 1", "formula": "eq_3"}]
  }
}
```

---

## 4.2 Formula Analyzer

### Invocation
- When MainAgent discovers formulas
- When user explicitly requests

### CRITICAL: Process ALL Formulas
- do NOT skip any formula, even if it appears similar to another
- Every equation in the paper must be analyzed and documented
- Check `processing_manifest.txt` to ensure all formulas are covered

### Input
```
- Formula content (LaTeX or description)
- Formula context (definition, assumptions)
- IDs of related formulas (already analyzed)
```

### Output Directory Structure
```
{output_dir}/formulas/{formula_id}/
├── report.md
├── summary.md
└── analysis.json
```

### JSON Format
```json
{
  "formula_id": "eq_3",
  "formula_content": "$$y = \\text{softmax}(\\frac{QK^T}{\\sqrt{d_k}})V$$",
  "source": "Page 3, Equation (3)",
  "variables": [
    {
      "symbol": "Q",
      "name": "Query",
      "type": "tensor",
      "shape": "[batch, heads, seq, d_k]",
      "shape_source": "Paper Section 3.2 | Code model.py:45",
      "physical_meaning": "Query vector for attention",
      "is_learnable": false,
      "is_hyperparameter": false,
      "from_where": "From input x via linear transform",
      "to_where": "To attention computation"
    }
  ],
  "functions": [
    {
      "name": "softmax",
      "type": "standard",
      "standard_library": "torch.nn.functional.softmax",
      "applied_to": "along last dimension"
    }
  ],
  "operations": [
    {
      "symbol": "QK^T",
      "type": "matrix_multiplication",
      "result_shape": "[batch, heads, seq, seq]",
      "explanation": "Q times K transpose"
    }
  ],
  "rigor_assessment": {
    "is_rigorous": true,
    "issues": [],
    "guesses": []
  },
  "cross_references": {
    "related_formulas": [{"formula_id": "eq_1", "relationship": "defines Q,K,V"}],
    "custom_functions_defined_elsewhere": []
  },
  "implementation_notes": {
    "code_correspondence": "model.py:Attention.forward()",
    "key_tricks": ["scaled_dot_product_attention"]
  },
  "uncertainty": {
    "guesses": [],
    "unconfirmed": [],
    "info_requests": []
  }
}
```

### Rigor Assessment
- If formula is not rigorous (e.g., omits broadcasting):
  - Mark: "Not rigorous: [issue]"
  - Provide guess with reason
  - Mark: `is_guess: true`, `confidence: "high|medium|low"`

---

## 4.3 Code Analyzer

### Invocation
- When paper provides open source link
- When user explicitly requests

### Input
```
- Repository URL
- Method name from paper
- Contribution type: architecture | training | data_augmentation | feature_engineering
```

### Output Directory Structure
```
{output_dir}/code/
├── report.md
├── summary.md
└── analysis.json
```

### JSON Format
```json
{
  "repository_url": "https://github.com/xxx/xxx",
  "local_path": "./code/xxx",
  "clone_confirmed": true,
  "analysis_focus": "architecture|training|...",
  "project_structure": {
    "root_files": ["README.md", "setup.py"],
    "core_files": [{"name": "model.py", "purpose": "Model definition"}],
    "subdirectories": {"models/": "Model def", "trainers/": "Training"}
  },
  "dependencies": {
    "python_version": "3.8+",
    "key_packages": ["torch", "transformers"],
    "requirements_file": "requirements.txt"
  },
  "modules": [
    {
      "id": "code_mod_1",
      "name": "class AttentionLayer",
      "path": "model.py:45",
      "functionality": "Multi-head attention",
      "inputs": [{"name": "query", "shape": "[B,H,S,D]"}],
      "outputs": [{"name": "output", "shape": "[B,H,S,D]"}],
      "internals": ["linear_qkv", "scaled_dot", "softmax"],
      "learnable_parameters": [{"name": "W_qkv", "shape": "[D,D]"}],
      "corresponds_to_paper_module": "fig_1:mod_attention",
      "corresponds_to_formulas": ["eq_3", "eq_4"]
    }
  ],
  "data_flow": [...],
  "paper_correspondence": {
    "modules": [...],
    "formulas": [...]
  },
  "reproducibility_checklist": [
    {"item": "Set random seed", "code_location": "train.py:20"}
  ]
}
```

---

## 4.4 Debug SubAgent (TDD)

### Invocation
- When MainAgent completes a module implementation
- To test the module

### Debug SubAgent Workflow (TDD Red-Green-Refactor)

```
Step 1: RED - Write failing test
  ↓
Write minimal test showing expected behavior
  ↓
Step 2: Verify RED - Watch it fail
  ↓
Run test, confirm fails correctly
  ↓
Step 3: GREEN - Minimal code (only if MainAgent requests modification)
  ↓
Write simplest code to pass
  ↓
Step 4: Verify GREEN - Watch it pass
  ↓
Step 5: REFACTOR - Clean up
  ↓
Step 6: Submit result to MainAgent
```

### Test Coverage Requirements

1. **Shape test**
   - Standard input shape
   - Different batch sizes
   - Different sequence lengths

2. **Hyperparameter enumeration**
   - Enumerate key hyperparameter combinations
   - Verify behavior under each

3. **Boundary conditions**
   - batch_size=1, seq_len=1
   - Extreme parameter values

4. **Dependency integration**
   - Can import from tested modules
   - I/O shapes match

5. **Numerical stability**
   - No NaN/Inf
   - Gradients correct

---

# Part 5: py File Standard

Each reproduction module must follow this structure:

```python
"""
Module: module_a.py
Function: [One sentence description]

Dependencies:
    - base.py (required)

Usage:
    from model.module_a import ModuleA
"""

import torch
import torch.nn as nn
from typing import Optional, Tuple
from .base import BaseModule


class ModuleAConfig:
    """Configuration for ModuleA"""
    def __init__(
        self,
        input_dim: int = 768,
        hidden_dim: int = 512,
        output_dim: int = 128,
        # Non-important params have defaults
        dropout: float = 0.1,
    ):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.dropout = dropout


class ModuleA(BaseModule):
    """
    ModuleA Implementation

    Hyperparameters:
        - input_dim: Input dimension, physical meaning is...
        - hidden_dim: Hidden dimension, physical meaning is...
        - output_dim: Output dimension, physical meaning is...
        - dropout: Dropout probability for regularization

    Input:
        - x: Tensor [batch_size, seq_len, input_dim]
        - mask: Optional[Tensor] [batch_size, seq_len]

    Output:
        - output: Tensor [batch_size, seq_len, output_dim]

    Physical meaning:
        - [What transformation is performed]
    """

    def __init__(self, config: ModuleAConfig):
        super().__init__()
        self.config = config
        # Implementation...

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        # Implementation...
        return output


# =============================================================================
# Test Code
# =============================================================================

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from log import get_logger
    logger = get_logger("module_a_test", log_dir="log")

    logger.info("=" * 60)
    logger.info("Testing ModuleA")
    logger.info("=" * 60)

    # Test 1: Basic shape
    config = ModuleAConfig(input_dim=768, hidden_dim=512, output_dim=128)
    model = ModuleA(config)
    x = torch.randn(2, 10, 768)
    output = model(x)
    assert output.shape == (2, 10, 128)
    logger.info("[PASS] Shape test")

    # Test 2: Hyperparameter enumeration
    for dropout in [0.0, 0.1, 0.3]:
        config = ModuleAConfig(dropout=dropout)
        model = ModuleA(config)
        output = model(x)
        assert output.shape == (2, 10, 128)
    logger.info("[PASS] Hyperparameter test")

    # Test 3: Numerical stability
    assert not torch.isnan(output).any()
    assert not torch.isinf(output).any()
    logger.info("[PASS] Numerical stability")

    logger.info("=" * 60)
    logger.info("All tests passed!")
    logger.info("=" * 60)
```

---

# Part 6: MainAgent Review Checklist

After receiving Debug SubAgent result, MainAgent MUST verify:

```
1. Code completeness
   - [ ] Implementation complete (no simplified functionality)
   - [ ] Hyperparameters exposed (not hardcoded)
   - [ ] Comments standardized

2. Test completeness
   - [ ] Shape test covered
   - [ ] Hyperparameter enumeration sufficient
   - [ ] Boundary conditions covered

3. Test quality
   - [ ] Tests truly verify functionality
   - [ ] Logs are clear
   - [ ] Debug process is reasonable

4. Functional consistency
   - [ ] Consistent with paper description
   - [ ] Consistent with formula definition
   - [ ] Consistent with open source code (if any)

5. Modification check
   - [ ] Did SubAgent modify planned functionality
   - [ ] Did it simplify complex functionality
   - [ ] If issues, require SubAgent to fix
```

---

# Part 7: Reproduction Directory Structure

```
{output_dir}/reproduction/
├── plan.md              # Real-time updated plan
├── README.md            # Integration guide
├── config.py            # Hyperparameters
├── requirements.txt
├── model/
│   ├── __init__.py
│   ├── base.py         # Smallest, no dependencies
│   ├── module_a.py
│   └── ...
├── data/
│   ├── __init__.py
│   └── preprocessing.py
├── loss/
│   ├── __init__.py
│   └── loss_xxx.py
├── train.py
├── evaluate.py
└── log/
    ├── module_a_test.log
    └── ...
```

---

# Part 8: README.md Template

```markdown
# Reproduction Project

## Project Overview
This is a reproduction of paper [Title](https://arxiv.org/abs/xxx).

## Quick Start

### Install Dependencies
```bash
pip install torch numpy transformers
```

### Basic Usage
```python
from config import ModelConfig
from model import ModuleA

config = ModelConfig(input_dim=768, hidden_dim=512)
model = ModuleA(config)
output = model(input_tensor)
```

## Module Description

### config.py
All hyperparameters.

### model/
| File | Class | Function |
|------|-------|----------|
| base.py | BaseModule | Base class |
| module_a.py | ModuleA | XXX |

### data/
Data preprocessing.

### loss/
Loss functions.

## Integration Guide

### Use Full Model
```python
from model import FullModel
model = FullModel(config)
```

### Use Single Module
```python
from model.module_a import ModuleA
module = ModuleA(custom_config)
```

### Replace Sub-module
```python
from model import ModuleA
from my_module import CustomModule

class ModifiedModel(ModuleA):
    def __init__(self, config):
        super().__init__(config)
        self.custom = CustomModule()
```

## Path Index
- Understanding: [UNDERSTANDING.md](../UNDERSTANDING.md)
- Analysis: [images/](images/) | [formulas/](formulas/) | [code/](code/)
```

---

# Part 9: Common SubAgent Rules

## Information Insufficient

**Prohibited:**
- Never guess without basis
- Never assume information not in context
- Never skip uncertain parts

**Correct approach:**
1. Mark: "Information insufficient: [specifically what's missing]"
2. Ask MainAgent for needed information
3. Continue after MainAgent supplements
4. If still unable to determine, mark as "unconfirmed"

**Request format:**
```
MainAgent, I need the following to continue:
- [Specific question 1]
- [Specific question 2]
- Needed context: [related section]
```

---

# Part 10: Language Convention

| Context | Language |
|---------|----------|
| Agent internal thinking | English |
| Agent-to-Agent communication | English |
| SubAgent calls | English |
| File content | English |
| User communication | Chinese |

---

# Part 11: Completion Criteria

MainAgent has completed when ALL:

1. ✅ All entities analyzed (images, formulas, code)
2. ✅ Cross-validation complete
3. ✅ UNDERSTANDING.md written with path indices
4. ✅ User confirmed
5. ✅ All modules implemented
6. ✅ All modules passed Debug SubAgent tests
7. ✅ MainAgent reviewed all test results
8. ✅ Full model integration test passed
9. ✅ README.md generated
10. ✅ plan.md contains complete interaction log

---

# Part 12: Error Handling

## Context Overflow
1. MainAgent detects context near limit
2. Request SubAgent to compress:
   - Keep: core findings, related entities, items to confirm
   - Delete: intermediate derivation, repeated descriptions
3. Continue after compression

## Persistent Errors
1. MainAgent records problem in progress.md
2. MainAgent reports to user:
   - Problem description
   - Completed analysis
   - Needed help
3. After user confirms, resume via file recovery
