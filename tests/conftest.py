"""Load the standalone API modules without requiring a full HA installation."""

from pathlib import Path
import sys
from types import ModuleType

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "fitssey"
package = ModuleType("fitssey")
package.__path__ = [str(PACKAGE_DIR)]
sys.modules.setdefault("fitssey", package)
