import numpy as np

from abtrust.stress import study_fixed_stress, study_gaussian_stress


def test_fixed_stress_exposes_selected_outcome_bias_and_handles_covariates():
    table = study_fixed_stress(n_sims=60)
    selected = table[table.scenario.str.startswith("selected") & (table.true_effect == 0)]
    assert (selected.bias > 0.3).all()
    assert (selected.rejection_rate > 0.8).all()
    valid = table[(table.scenario == "correlated covariates") & (table.true_effect == 0)]
    assert set(valid.method) == {"welch", "cuped", "lin_hc2"}
    assert (valid.coverage >= 0.85).all()
    assert not table.isna().any().any()
    deterministic = table[table.scenario == "constant outcomes"]
    assert (deterministic.coverage == 1).all()
    assert (deterministic.bias == 0).all()


def test_known_gaussian_stress_measures_simultaneous_coverage():
    table = study_gaussian_stress(n_sims=120)
    null = table[table.true_effect == 0]
    assert set(null.looks) == {1, 20, 100}
    assert (null.rejection_rate < 0.1).all()
    assert (table.simultaneous_coverage > 0.9).all()
    assert np.allclose(null.rejection_rate + null.simultaneous_coverage, 1)
    assert (table.mean_sample_fraction.between(0, 1)).all()
