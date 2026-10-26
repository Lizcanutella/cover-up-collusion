# Third-party code

Parts of this repository are adapted from **joint-task-collusion**, a fork of
[SALT-NLP/agent-collusion](https://github.com/SALT-NLP/agent-collusion) (Shi, Zhang, Yang 2026,
"Emergent Collusion in Long-Horizon LLM Agent Interaction"), some of it by way of our own earlier, unpublished
code, which adapted and tested it first.

| File here | Adapted from | By way of our earlier code |
| --- | --- | --- |
| `coverup/llm.py` | `experiments/llm.py` (provider routing, the prompt-cache breakpoint, reasoning replay) and `experiments/agents.py` (tool-call normalisation, error classification, retries) | the client, retry loop and refusal handling |
| `coverup/usage.py` | `experiments/usage.py` (usage normalisation and summaries) | copied unchanged |
| `coverup/sandbox.py` | `experiments/protocol/code_tests.py` (the bubblewrap command, interpreter mounts, sandbox probe, bounded output reader) | — |

That code is distributed under the following licence:

```text
MIT License

Copyright (c) 2026 Xinrui Shi, Yanzhe Zhang, and Diyi Yang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The experimental protocol borrows from two papers, which released no code; see `CREDITS.md`.
