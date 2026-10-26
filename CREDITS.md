# Credits: protocols borrowed from published work

Neither paper below released code (checked 2026-10-17), so nothing here is their code. We borrow measurement
designs and cite them wherever they are used.

**Sun, Wang, Zhu, Li, Zhao, Yuan (2026).** *When "Must" Becomes "Maybe": Erosion of Workflow Constraints in LLM
Agent Handoffs.* arXiv:2608.24569.
- The four-field representation of a blocker (stop status, prerequisite, responsible owner, fallback), which the
  warnings in both scenarios' `scenario.yaml` are written to carry.
- The fixed-artifact design: every model in a cell receives the same scripted messages (the peer's note, the lead's
  request, the workers' reports), so only the manipulated sentence differs between cells.
- Measuring the record separately from the action (`coverup/score.py` scores the final report beside the diff).

**Ying, Yan, Luo, Zou, Liu, Liu (2026).** *Delegated Misalignment: How Multi-Agent Structures Amplify LLM Safety
Risks.* EMNLP 2026, arXiv:2609.27900.
- Keeping the solo and team prompts identical apart from the manipulated factor (their delegation conditions added
  performance pressure that their single-agent baseline lacked; `coverup/prompts.py` avoids that).

Borrowed code is listed in `THIRD_PARTY_LICENSES.md`.
