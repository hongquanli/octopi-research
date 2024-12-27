import control.microscope

def test_create_simulated_microscope():
    sim_scope = control.microscope.Microscope(is_simulation=True)