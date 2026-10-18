"""abtrust: statistical experiment analysis and empirical validation.

Monte Carlo simulation checks selected methods in specified settings; it cannot
prove a general type-I error guarantee. See docs/methods.md for assumptions.
"""

from .checks import SRMResult, srm_by_segment, srm_test
from .design import SampleSize, mde_mean, power_mean, sample_size_mean, sample_size_proportion
from .estimators import Estimate, cuped, lin_adjustment, ratio_delta, welch_ttest
from .multiple import adjust, benjamini_hochberg, holm
from .readout import Metric, Readout, analyze
from .sequential import SequentialResult, sequential_test, tau_for_horizon, tau_from_design

__version__ = "0.3.0"

__all__ = [
    "Estimate",
    "Metric",
    "Readout",
    "SRMResult",
    "SampleSize",
    "SequentialResult",
    "adjust",
    "analyze",
    "benjamini_hochberg",
    "cuped",
    "holm",
    "lin_adjustment",
    "mde_mean",
    "power_mean",
    "ratio_delta",
    "sample_size_mean",
    "sample_size_proportion",
    "sequential_test",
    "srm_by_segment",
    "srm_test",
    "tau_for_horizon",
    "tau_from_design",
    "welch_ttest",
]
