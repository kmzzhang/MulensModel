import numpy as np
from math import cos, sin
import matplotlib.pyplot as plt

from MulensModel.utils import Utils


class CausticsPointWithShear(Caustics):
    """
    Class for the caustic structure corresponding to a given (*q*, *s*),
    i.e. mass ratio and separation. Implemented for 2-body lenses only.

    Attributes :
        q: *float*
            mass ratio between the 2 bodies; always <= 1
        s: *float*
            separation between the 2 bodies (as a fraction of the
            Einstein ring)
    """

    def __init__(self, convergence_K, shear_G):
        # Set K, G
        self.convergence_K = convergence_K
        self.shear_G = shear_G

        # Set place holder variables
        self._x = None
        self._y = None
        self._critical_curve = None

    def _calculate(self, n_points=5000):
        """
        Solve the caustics polynomial to calculate the critical curve
        and caustic structure.

        Based on Eq. 6 Cassan 2008 modified so origin is center of
        mass and larger mass is on the left. Uses complex coordinates.
        """
        # Find number of angles so that 4*n_angles is the multiple of 4 that
        # is closest to n_points.
        n_angles = int(n_points/4.+.5)

        # Initialize variables
        self._x = []
        self._y = []
        self._critical_curve = self.CriticalCurve()

        # Solve for the critical curve (and caustic) in complex coordinates.
        for phi in np.linspace(0., 2.*np.pi, n_angles, endpoint=False):
            # Change the angle to a complex number
            eiphi = np.complex(cos(phi), -sin(phi))
            soln = sqrt(1/((1-self.convergence_K)*eiphi + self.shear_G.conjugate()))
            roots = np.array([soln, -soln])
            # Store results
            for root in roots:
                self._critical_curve.x.append(root.real)
                self._critical_curve.y.append(root.imag)

                source_plane_position = self._solve_lens_equation(root)
                self._x.append(source_plane_position.real)
                self._y.append(source_plane_position.imag)

    def _solve_lens_equation(self, complex_value):
        """
        Solve the lens equation for the given point (in complex coordinates).
        """
        complex_conjugate = np.conjugate(complex_value)
        return ((1-self.convergence_K)*complex_value 
                - self.shear_G*complex_conjugate
                - (1./complex_conjugate))