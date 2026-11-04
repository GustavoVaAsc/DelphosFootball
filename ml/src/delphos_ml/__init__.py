"""DelphosFootball shared ML package.

Input: none (package facade).
Output: `load_model` for the ARCHITECTURE.md section 4.3 artifact contract.
Responsibility: holds the pipeline settings (`config`), feature/model libraries, artifact loader
(`artifacts`), and offline pipeline stages (`pipeline`).
"""

from delphos_ml.artifacts import load_model

__all__ = ["load_model"]
