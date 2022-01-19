"""
Example use of MulensModel to model a single source binary lens with an
external mass sheet, as in Peirson et al. 2022 ApJ,
Vedantham et al. 2017 ApJ 845, 89.
Binary lens with external mass sheet assumes a point source when using VBBL.
"""

import numpy as np
import matplotlib.pyplot as plt

import MulensModel as mm


# Define lens model and source parameters
s = 1.0
q = 0.01
alpha = 270
K = 0.1
G = complex(0.05, 0.0)
t_0 = 300
t_E = 500
rho = 1.e-4
u_0 = -0.07

time = np.arange(t_0-75., t_0+75., 0.1, dtype=float)

lens = mm.model.Model({
        't_0': t_0, 'u_0': u_0, 't_E': t_E, 's': s, 'q': q, 'alpha': alpha,
        'convergence_K': K, 'shear_G': G, 'rho': rho})
no_shear = mm.model.Model({'t_0': t_0, 'u_0': u_0, 't_E': t_E, 's': s, 'q': q,
                           'alpha': alpha, 'rho': rho})

lens.set_magnification_methods([min(time), 'vbbl', max(time)])
no_shear.set_magnification_methods([min(time), 'vbbl', max(time)])

# Plot magnification curve and caustics
(fig, (ax1, ax2)) = plt.subplots(figsize=(10, 5), ncols=2)

ax1.plot(time, lens.get_magnification(time), color='r')
ax1.plot(time, no_shear.get_magnification(time), alpha=0.4)

ax2.set_xlim(-0.16, 0.32)
ax2.set_ylim(-0.25, 0.25)
ax2.set_xlabel("x", fontweight="bold")
ax2.set_ylabel("y", fontweight="bold")
lens.plot_trajectory(t_range=[t_0 - 75, t_0], caustics=True, color='green')
lens.plot_trajectory(t_range=[t_0, t_0 + 75], color='blue')

mm.Caustics(s=s, q=q).plot(alpha=0.3)  # no_shear

plt.show()
