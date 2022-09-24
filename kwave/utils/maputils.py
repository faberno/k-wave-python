import math
from math import floor
from typing import Tuple, Optional

import matplotlib.pyplot as plt
import numpy as np
from kwave.utils.matrixutils import matlab_find
from scipy import optimize
import warnings

from kwave.utils.conversionutils import db2neper, neper2db


def get_spaced_points(start, stop, n=100, spacing='linear'):
    """
    getSpacedPoints generates a row vector of either logarithmically or
    linearly spaced points between X1 and X2. When spacing is set to
    'linear', the function is identical to the inbuilt np.linspace
    function. When spacing is set to 'log', the function is similar to
    the inbuilt np.logspace function, except that X1 and X2 define the start
    and end numbers, not decades. For logarithmically spaced points, X1
    must be > 0. If N < 2, X2 is returned.
    Args:
        start:
        stop:
        n:
        spacing:

    Returns:
        points:
    """
    # check if the end point is larger than the start point
    if stop <= start:
        raise ValueError('X2 must be larger than X1.')

    if spacing == 'linear':
        return np.linspace(start, stop, num=n)
    elif spacing == 'log':
        return np.geomspace(start, stop, num=n)
    else:
        raise ValueError(f"spacing {spacing} is not a valid argument. Choose from 'linear' or 'log'.")


def fit_power_law_params(a0, y, c0, f_min, f_max, plot_fit=False):
    """

    fit_power_law_params calculates the absorption parameters that should
    be defined in the simulation functions given the desired power law
    absorption behaviour defined by a0 and y. This takes into account the
    actual absorption behaviour exhibited by the fractional Laplacian
    wave equation.

    This fitting is required when using large absorption values or high
    frequencies, as the fractional Laplacian wave equation solved in
    kspaceFirstOrderND and kspaceSecondOrder no longer encapsulates
    absorption of the form a = a0*f^y.

    The returned values should be used to define the medium.alpha_coeff
    and medium.alpha_power within the simulation functions. The
    absorption behaviour over the frequency range f_min:f_max will then
    follow the power law defined by a0 and y.Add testing for getOptimalPMLSize()

    Args:
        a0:
        y:
        c0:
        f_min:
        f_max:
        plot_fit:

    Returns:
        a0_fit:
        y_fit:

    """
    # define frequency axis
    f = get_spaced_points(f_min, f_max, 200)
    w = 2 * np.pi * f
    # convert user defined a0 to Nepers/((rad/s)^y m)
    a0_np = db2neper(a0, y)

    desired_absorption = a0_np * w ** y

    def abs_func(trial_vals):
        """Second-order absorption error"""
        a0_np_trial, y_trial = trial_vals

        actual_absorption = a0_np_trial * w ** y_trial / (1 - (y_trial + 1) * \
                                                          a0_np_trial * c0 * np.tan(np.pi * y_trial / 2) * w ** (
                                                                      y_trial - 1))

        absorption_error = np.sqrt(np.sum((desired_absorption - actual_absorption) ** 2))

        return absorption_error

    a0_np_fit, y_fit = optimize.fmin(abs_func, [a0_np, y])

    a0_fit = neper2db(a0_np_fit, y_fit)

    if plot_fit:
        raise NotImplementedError

    return a0_fit, y_fit


def power_law_kramers_kronig(w, w0, c0, a0, y):
    """
     POWERLAWKRAMERSKRONIG Calculate dispersion for power law absorption.

     DESCRIPTION:
         powerLawKramersKronig computes the variation in sound speed for an
         attenuating medium using the Kramers-Kronig for power law
         attenuation where att = a0*w^y. The power law parameters must be in
         Nepers / m, with the frequency in rad/s. The variation is given
         about the sound speed c0 at a reference frequency w0.

     USAGE:
         c_kk = power_law_kramers_kronig(w, w0, c0, a0, y)

     INPUTS:

     OUTPUTS:

    Args:
         w:             input frequency array [rad/s]
         w0:            reference frequency [rad/s]
         c0:            sound speed at w0 [m/s]
         a0:            power law coefficient [Nepers/((rad/s)^y m)]
         y:             power law exponent, where 0 < y < 3

    Returns:
         c_kk           variation of sound speed with w [m/s]

    """
    if 0 >= y or y >= 3:
        warnings.warn("y must be within the interval (0,3)", UserWarning)
        c_kk = c0 * np.ones_like(w)
    elif y == 1:
        # Kramers-Kronig for y = 1
        c_kk = 1 / (1 / c0 - 2 * a0 * np.log(w / w0) / np.pi)
    else:
        # Kramers-Kronig for 0 < y < 1 and 1 < y < 3
        c_kk = 1 / (1 / c0 + a0 * np.tan(y * np.pi / 2) * (w ** (y - 1) - w0 ** (y - 1)))

    return c_kk


def water_absorption(f, temp):
    """
    water_absorption Calculate ultrasound absorption in distilled water.

    DESCRIPTION:
    waterAbsorption calculates the ultrasonic absorption in distilled
    water at a given temperature and frequency using a 7 th order
    polynomial fitted to the data given by np.pinkerton(1949).

    USAGE:
    abs = waterAbsorption(f, T)

    INPUTS:
    f - f frequency value [MHz]
    T - water temperature value [degC]

    OUTPUTS:
    abs - absorption[dB / cm]

    REFERENCES:
    [1] np.pinkerton(1949) "The Absorption of Ultrasonic Waves in Liquids
    and its Relation to Molecular Constitution, " Proceedings of the
    Physical Society.Section B, 2, 129 - 141

    """

    NEPER2DB = 8.686
    # check temperature is within range
    if not 0 <= temp <= 60:
        raise Warning("Temperature outside range of experimental data")

    # conversion factor between Nepers and dB NEPER2DB = 8.686;
    # coefficients for 7th order polynomial fit
    a = [56.723531840522710, -2.899633796917384, 0.099253401567561, -0.002067402501557, 2.189417428917596e-005,
         -6.210860973978427e-008, -6.402634551821596e-010, 3.869387679459408e-012]

    # TODO: this is not a vectorized version of this function. This is different than the MATLAB version
    # make sure vectors are in the correct orientation
    # T = reshape(T, 3, []);
    # f = reshape(f, [], 1);

    # compute absorption
    a_on_fsqr = (a[0] + a[1] * temp + a[2] * temp ** 2 + a[3] * temp ** 3 + a[4] * temp ** 4 + a[5] * temp ** 5 + a[
        6] * temp ** 6 + a[7] * temp ** 7) * 1e-17

    abs = NEPER2DB * 1e12 * f ** 2 * a_on_fsqr
    return abs


def hounsfield2soundspeed(ct_data):
    """

    Calclulates the soundspeed of a medium given a CT of the medium.
    For soft-tissue, the approximate sound speed can also be returned
    using the empirical relationship given by Mast.

    Mast, T. D., "Empirical relationships between acoustic parameters
    in human soft tissues," Acoust. Res. Lett. Online, 1(2), pp. 37-42
    (2000).

    Args:
        ct_data: 

    Returns: sound_speed:       matrix of sound speed values of size of ct data

    """
    # calculate corresponding sound speed values if required using soft tissue  relationship
    # TODO confirm that this linear relationship is correct
    sound_speed = (hounsfield2density(ct_data) + 349) / 0.893

    return sound_speed


def hounsfield2density(ct_data, plot_fitting=False):
    """
    Convert Hounsfield units in CT data to density values [kg / m ^ 3]
    based on the experimental data given by Schneider et al.
    The conversion is made using a np.piece-wise linear fit to the data.

    Args:
        ct_data:
        plot_fitting:

    Returns:
        density_map:            density in kg / m ^ 3
    """
    # create empty density matrix
    density = np.zeros(ct_data.shape, like=ct_data)

    # apply conversion in several parts using linear fits to the data
    # Part 1: Less than 930 Hounsfield Units
    density[ct_data < 930] = np.polyval([1.025793065681423, -5.680404011488714], ct_data[ct_data < 930])

    # Part 2: Between 930 and 1098(soft tissue region)
    index_selection = np.logical_and(930 <= ct_data, ct_data <= 1098)
    density[index_selection] = np.polyval([0.9082709691264, 103.6151457847139],
                                          ct_data[index_selection])

    # Part 3: Between 1098 and 1260(between soft tissue and bone)
    index_selection = np.logical_and(1098 < ct_data, ct_data < 1260)
    density[index_selection] = np.polyval([0.5108369316599, 539.9977189228704], ct_data[index_selection])

    # Part 4: Greater than 1260(bone region)
    density[ct_data >= 1260] = np.polyval([0.6625370912451, 348.8555178455294], ct_data[ct_data >= 1260])

    if plot_fitting:
        raise NotImplementedError("Plotting function not implemented in Python")

    return density


def water_sound_speed(temp):
    """
    WATERSOUNDSPEED Calculate the sound speed in distilled water with temperature.

     DESCRIPTION:
         waterSoundSpeed calculates the sound speed in distilled water at a
         a given temperature using the 5th order polynomial given by Marczak
         (1997).

     USAGE:
         c = waterSoundSpeed(T)

     INPUTS:
         T             - water temperature in the range 0 to 95 [degC]

     OUTPUTS:
         c             - sound speed [m/s]

     REFERENCES:
         [1] Marczak (1997) "Water as a standard in the measurements of speed
         of sound in liquids," J. Acoust. Soc. Am., 102, 2776-2779.

    """

    # check limits
    assert 95 >= temp >= 0, "temp must be between 0 and 95."

    # find value
    p = [2.787860e-9, -1.398845e-6, 3.287156e-4, -5.779136e-2, 5.038813, 1.402385e3]
    c = np.polyval(p, temp)
    return c


def water_density(temp):
    """
     WATERDENSITY Calculate density of air - saturated water with temperature.

     DESCRIPTION:
     waterDensity calculates the density of air - saturated water at a given % temperature using the 4 th order polynomial given by Jones(1992).

     USAGE:
     density = waterDensity(T)

     INPUTS:
     T - water temperature in the range 5 to 40[degC]

     OUTPUTS:
     density - density of water[kg / m ^ 3]

     ABOUT:
     author - Bradley E.Treeby
     date - 22 nd February 2018
     last update - 4 th April 2019

     REFERENCES:
     [1] F.E.Jones and G.L.Harris(1992) "ITS-90 Density of Water
     Formulation for Volumetric Standards Calibration, " J. Res. Natl.
     Inst.Stand.Technol., 97(3), 335 - 340.
     """
    # check limits
    assert 5 <= temp <= 40, "T must be between 5 and 40."

    # calculate density of air - saturated water
    density = 999.84847 + 6.337563e-2 * temp - 8.523829e-3 * temp ** 2 + 6.943248e-5 * temp ** 3 - 3.821216e-7 * temp ** 4
    return density


def water_non_linearity(temp):
    """
     WATERNONLINEARITY Calculate B/A of water with temperature.

     DESCRIPTION:
         waterNonlinearity calculates the parameter of nonlinearity B/A at a
         given temperature using a fourth-order polynomial fitted to the data
         given by Beyer (1960).

     USAGE:
         BonA = waterNonlinearity(T)

     INPUTS:
         T             - water temperature in the range 0 to 100 [degC]

     OUTPUTS:
         BonA          - parameter of nonlinearity

     ABOUT:
         author        - Bradley E. Treeby
         date          - 22nd February 2018
         last update   - 4th April 2019

     REFERENCES:
         [1] R. T Beyer (1960) "Parameter of nonlinearity in fluids," J.
         Acoust. Soc. Am., 32(6), 719-721.

    """

    # check limits
    assert 0 <= temp <= 100, "Temp must be between 0 and 100."

    # find value
    p = [-4.587913769504693e-08, 1.047843302423604e-05, -9.355518377254833e-04, 5.380874771364909e-2, 4.186533937275504]
    BonA = np.polyval(p, temp);
    return BonA


def makeBall(Nx, Ny, Nz, cx, cy, cz, radius, plot_ball=False, binary=False):
    """
    MAKEBALL Create a binary map of a filled ball within a 3D grid.

    DESCRIPTION:
         makeBall creates a binary map of a filled ball within a
         three-dimensional grid (the ball position is denoted by 1's in the
         matrix with 0's elsewhere). A single grid point is taken as the ball
         centre thus the total diameter of the ball will always be an odd
         number of grid points.
    Args:
        Nx: size of the 3D grid in x-dimension [grid points]
        Ny: size of the 3D grid in y-dimension [grid points]
        Nz: size of the 3D grid in z-dimension [grid points]
        cx: centre of the ball in x-dimension [grid points]
        cy: centre of the ball in y-dimension [grid points]
        cz: centre of the ball in z-dimension [grid points]
        radius: ball radius [grid points]
        plot_ball: Boolean controlling whether the ball is plotted using voxelPlot (default = false)
        binary: Boolean controlling whether the ball map is returned as a double precision matrix (false)
                or a logical matrix (true) (default = false)

    Returns:
        3D binary map of a filled ball
    """
    # define literals
    MAGNITUDE = 1

    # force integer values
    Nx = int(round(Nx))
    Ny = int(round(Ny))
    Nz = int(round(Nz))
    cx = int(round(cx))
    cy = int(round(cy))
    cz = int(round(cz))

    # check for zero values
    if cx == 0:
        cx = int(floor(Nx / 2)) + 1

    if cy == 0:
        cy = int(floor(Ny / 2)) + 1

    if cz == 0:
        cz = int(floor(Nz / 2)) + 1

    # create empty matrix
    ball = np.zeros((Nx, Ny, Nz)).astype(np.bool if binary else np.float32)

    # define np.pixel map
    r = makePixelMap(Nx, Ny, Nz, 'Shift', [0, 0, 0])

    # create ball
    ball[r <= radius] = MAGNITUDE

    # shift centre
    cx = cx - int(math.ceil(Nx / 2))
    cy = cy - int(math.ceil(Ny / 2))
    cz = cz - int(math.ceil(Nz / 2))
    ball = np.roll(ball, (cx, cy, cz), axis=(0, 1, 2))

    # plot results
    if plot_ball:
        raise NotImplementedError
        # voxelPlot(double(ball))
    return ball


def makeDisc(Nx, Ny, cx, cy, radius, plot_disc=False):
    """
        Create a binary map of a filled disc within a 2D grid.

             makeDisc creates a binary map of a filled disc within a
             two-dimensional grid (the disc position is denoted by 1's in the
             matrix with 0's elsewhere). A single grid point is taken as the disc
             centre thus the total diameter of the disc will always be an odd
             number of grid points. As the returned disc has a constant radius, if
             used within a k-Wave grid where dx ~= dy, the disc will appear oval
             shaped. If part of the disc overlaps the grid edge, the rest of the
             disc will wrap to the grid edge on the opposite side.
    Args:
        Nx:
        Ny:
        cx:
        cy:
        radius:
        plot_disc:

    Returns:

    """
    # define literals
    MAGNITUDE = 1

    # force integer values
    Nx = int(round(Nx))
    Ny = int(round(Ny))
    cx = int(round(cx))
    cy = int(round(cy))

    # check for zero values
    if cx == 0:
        cx = int(floor(Nx / 2)) + 1

    if cy == 0:
        cy = int(floor(Ny / 2)) + 1

    # check the inputs
    assert (0 <= cx < Nx) and (0 <= cy < Ny), 'Disc center must be within grid.'

    # create empty matrix
    disc = np.zeros((Nx, Ny))

    # define np.pixel map
    r = makePixelMap(Nx, Ny, None, 'Shift', [0, 0])

    # create disc
    disc[r <= radius] = MAGNITUDE

    # shift centre
    cx = cx - int(math.ceil(Nx / 2))
    cy = cy - int(math.ceil(Ny / 2))
    disc = np.roll(disc, (cx, cy), axis=(0, 1))

    # create the figure
    if plot_disc:
        raise NotImplementedError
    return disc


def makeCircle(Nx, Ny, cx, cy, radius, arc_angle=None, plot_circle=False):
    """
        Create a binary map of a circle within a 2D grid.

             makeCircle creates a binary map of a circle or arc (using the
             midpoint circle algorithm) within a two-dimensional grid (the circle
             position is denoted by 1's in the matrix with 0's elsewhere). A
             single grid point is taken as the circle centre thus the total
             diameter will always be an odd number of grid points.

             Note: The centre of the circle and the radius are not constrained by
             the grid dimensions, so it is possible to create sections of circles,
             or a blank image if none of the circle intersects the grid.
    Args:
        Nx:
        Ny:
        cx:
        cy:
        radius:
        plot_disc:

    Returns:

    """
    # define literals
    MAGNITUDE = 1

    if arc_angle is None:
        arc_angle = 2 * np.pi
    elif arc_angle > 2 * np.pi:
        arc_angle = 2 * np.pi
    elif arc_angle < 0:
        arc_angle = 0

    # force integer values
    Nx = int(round(Nx))
    Ny = int(round(Ny))
    cx = int(round(cx))
    cy = int(round(cy))
    radius = int(round(radius))

    # check for zero values
    if cx == 0:
        cx = int(floor(Nx / 2)) + 1

    if cy == 0:
        cy = int(floor(Ny / 2)) + 1

    # create empty matrix
    circle = np.zeros((Nx, Ny), dtype=int)

    # initialise loop variables
    x = 0
    y = radius
    d = 1 - radius

    if (cx >= 1) and (cx <= Nx) and ((cy - y) >= 1) and ((cy - y) <= Ny):
        circle[cx - 1, cy - y - 1] = MAGNITUDE

    # draw the remaining cardinal points
    px = [cx, cx + y, cx - y]
    py = [cy + y, cy, cy]
    for point_index, (px_i, py_i) in enumerate(zip(px, py)):
        # check whether the point is within the arc made by arc_angle, and lies
        # within the grid
        if (np.arctan2(px_i - cx, py_i - cy) + np.pi) <= arc_angle:
            if (px_i >= 1) and (px_i <= Nx) and (py_i >= 1) and (
                    py_i <= Ny):
                circle[px_i - 1, py_i - 1] = MAGNITUDE

    # loop through the remaining points using the midpoint circle algorithm
    while x < (y - 1):

        x = x + 1
        if d < 0:
            d = d + x + x + 1
        else:
            y = y - 1
            a = x - y + 1
            d = d + a + a

        # setup point indices (break coding standard for readability)
        px = [x + cx, y + cx, y + cx, x + cx, -x + cx, -y + cx, -y + cx, -x + cx]
        py = [y + cy, x + cy, -x + cy, -y + cy, -y + cy, -x + cy, x + cy, y + cy]

        # loop through each point
        for point_index, (px_i, py_i) in enumerate(zip(px, py)):

            # check whether the point is within the arc made by arc_angle, and
            # lies within the grid
            if (np.arctan2(px_i - cx, py_i - cy) + np.pi) <= arc_angle:
                if (px_i >= 1) and (px_i <= Nx) and (py_i >= 1) and (py_i <= Ny):
                    circle[px_i - 1, py_i - 1] = MAGNITUDE

    if plot_circle:
        plt.imshow(circle, cmap='gray_r')
        plt.ylabel('x-position [grid points]')
        plt.xlabel('y-position [grid points]')
        plt.show()

    return circle


def makeCartCircle(radius, num_points, center_pos=None, arc_angle=(2 * np.pi), plot_circle=False):
    """
        Create a 2D Cartesian circle or arc.

             MakeCartCircle creates a 2 x num_points array of the Cartesian
             coordinates of points evenly distributed over a circle or arc (if
             arc_angle is given).
    Args:

    Returns:

    """
    full_circle = (arc_angle == 2 * np.pi)

    if center_pos is None:
        cx = cy = 0
    else:
        cx, cy = center_pos

    # ensure there is only a total of num_points including the endpoints when
    # arc_angle is not equal to 2*pi
    if not full_circle:
        num_points = num_points - 1

    # create angles
    angles = np.arange(0, num_points + 1) * arc_angle / num_points + np.pi / 2

    # discard repeated final point if arc_angle is equal to 2*pi
    if full_circle:
        angles = angles[0:- 1]

    # create cartesian grid
    # circle = flipud([radius*cos(angles); radius*sin(-angles)]);        # B.0.3
    circle = np.vstack([radius * np.cos(angles), radius * np.sin(-angles)])  # B.0.4

    # offset if needed
    circle[0, :] = circle[0, :] + cx
    circle[1, :] = circle[1, :] + cy

    if plot_circle:
        raise NotImplementedError

    return circle


def makePixelMap(Nx, Ny, Nz=None, *args):
    """
    MAKEPIXELMAP Create matrix of grid point distances from the centre point.

     DESCRIPTION:
         makePixelMap generates a matrix populated with values of how far each
         pixel in a grid is from the centre (given in pixel coordinates). Both
         single and double pixel centres can be used by setting the optional
         input parameter 'OriginSize'. For grids where the dimension size and
         centre pixel size are not both odd or even, the optional input
         parameter 'Shift' can be used to control the location of the
         centerpoint.

         examples for a 2D pixel map:

         Single pixel origin size for odd and even (with 'Shift' = [1 1] and
         [0 0], respectively) grid sizes:

         x x x       x x x x         x x x x
         x 0 x       x x x x         x 0 x x
         x x x       x x 0 x         x x x x
                     x x x x         x x x x

         Double pixel origin size for even and odd (with 'Shift' = [1 1] and
         [0 0], respectively) grid sizes:

         x x x x      x x x x x        x x x x x
         x 0 0 x      x x x x x        x 0 0 x x
         x 0 0 x      x x 0 0 x        x 0 0 x x
         x x x x      x x 0 0 x        x x x x x
                      x x x x x        x x x x x

         By default a single pixel centre is used which is shifted towards
         the final row and column.
    Args:
        *args:

    Returns:

    """
    # define defaults
    origin_size = 'single'
    shift_def = 1

    # detect whether the inputs are for two or three dimensions
    if Nz is None:
        map_dimension = 2
        shift = [shift_def, shift_def]
    else:
        map_dimension = 3
        shift = [shift_def, shift_def, shift_def]

    # replace with user defined values if provided
    if len(args) > 0:
        assert len(args) % 2 == 0, 'Optional inputs must be entered as param, value pairs.'
        for input_index in range(0, len(args), 2):
            if args[input_index] == 'Shift':
                shift = args[input_index + 1]
            elif args[input_index] == 'OriginSize':
                origin_size = args[input_index + 1]
            else:
                raise ValueError('Unknown optional input.')

    # catch input errors
    assert origin_size in ['single', 'double'], 'Unknown setting for optional input Center.'

    assert len(
        shift) == map_dimension, f'Optional input Shift must have {map_dimension} elements for {map_dimension} dimensional input parameters.'

    if map_dimension == 2:
        # create the maps for each dimension
        nx = createPixelDim(Nx, origin_size, shift[0])
        ny = createPixelDim(Ny, origin_size, shift[1])

        # create plaid grids
        r_x, r_y = np.meshgrid(nx, ny, indexing='ij')

        # extract the pixel radius
        r = np.sqrt(r_x ** 2 + r_y ** 2)
    if map_dimension == 3:
        # create the maps for each dimension
        nx = createPixelDim(Nx, origin_size, shift[0])
        ny = createPixelDim(Ny, origin_size, shift[1])
        nz = createPixelDim(Nz, origin_size, shift[2])

        # create plaid grids
        r_x, r_y, r_z = np.meshgrid(nx, ny, nz, indexing='ij')

        # extract the pixel radius
        r = np.sqrt(r_x ** 2 + r_y ** 2 + r_z ** 2)
    return r


def createPixelDim(Nx, origin_size, shift):
    # Nested function to create the pixel radius variable

    # grid dimension has an even number of points
    if Nx % 2 == 0:

        # pixel numbering has a single centre point
        if origin_size == 'single':

            # centre point is shifted towards the final pixel
            if shift == 1:
                nx = np.arange(-Nx / 2, Nx / 2 - 1 + 1, 1)

            # centre point is shifted towards the first pixel
            else:
                nx = np.arange(-Nx / 2 + 1, Nx / 2 + 1, 1)

        # pixel numbering has a double centre point
        else:
            nx = np.hstack([np.arange(-Nx / 2 + 1, 0 + 1, 1), np.arange(0, -Nx / 2 - 1 + 1, 1)])

    # grid dimension has an odd number of points
    else:

        # pixel numbering has a single centre point
        if origin_size == 'single':
            nx = np.arange(-(Nx - 1) / 2, (Nx - 1) / 2 + 1, 1)

        # pixel numbering has a double centre point
        else:

            # centre point is shifted towards the final pixel
            if shift == 1:
                nx = np.hstack([np.arange(-(Nx - 1) / 2, 0 + 1, 1), np.arange(0, (Nx - 1) / 2 - 1 + 1, 1)])

            # centre point is shifted towards the first pixel
            else:
                nx = np.hstack([np.arange(-(Nx - 1) / 2 + 1, 0 + 1, 1), np.arange(0, (Nx - 1) / 2 + 1, 1)])
    return nx


def makeLine(
        Nx: int,
        Ny: int,
        startpoint: Tuple[int, int],
        endpoint: Optional[Tuple[int, int]] = None,
        angle: Optional[float] = None,
        length: Optional[int] = None
) -> np.ndarray:
    # =========================================================================
    # INPUT CHECKING
    # =========================================================================

    startpoint = np.array(startpoint, dtype=int)
    if endpoint is not None:
        endpoint = np.array(endpoint, dtype=int)

    if len(startpoint) != 2:
        raise ValueError('startpoint should be a two-element vector.')

    if np.any(startpoint < 1) or startpoint[0] > Nx or startpoint[1] > Ny:
       ValueError('The starting point must lie within the grid, between [1 1] and [Nx Ny].')

    # =========================================================================
    # LINE BETWEEN TWO POINTS OR ANGLED LINE?
    # =========================================================================

    if endpoint is not None:
        linetype = 'AtoB'
        a, b = startpoint, endpoint

        # Addition => Fix Matlab2Python indexing
        a -= 1
        b -= 1
    else:
        linetype = 'angled'
        angle, linelength = angle, length

    # =========================================================================
    # MORE INPUT CHECKING
    # =========================================================================

    if linetype == 'AtoB':

        # a and b must be different points
        if np.all(a == b):
            raise ValueError('The first and last points cannot be the same.')

        # end point must be a two-element row vector
        if len(b) != 2:
            raise ValueError('endpoint should be a two-element vector.')

        # a and b must be within the grid
        xx = np.array([a[0], b[0]], dtype=int)
        yy = np.array([a[1], b[1]], dtype=int)
        if np.any(a < 0) or np.any(b < 0) or np.any(xx > Nx - 1) or np.any(yy > Ny - 1):
           raise ValueError('Both the start and end points must lie within the grid.')

    if linetype == 'angled':

        # angle must lie between -np.pi and np.pi
        angle = angle %  (2 * np.pi)
        if angle > np.pi:
            angle = angle - (2 * np.pi)
        elif angle < -np.pi:
            angle = angle + (2 * np.pi)

    # =========================================================================
    # CALCULATE A LINE FROM A TO B
    # =========================================================================

    if linetype == 'AtoB':

        # define an empty grid to hold the line
        line = np.zeros((Nx, Ny))

        # find the equation of the line
        m = (b[1] - a[1]) / (b[0] - a[0])    # gradient of the line
        c = a[1] - m * a[0]                  # where the line crosses the y axis

        if abs(m) < 1:

            # start at the end with the smallest value of x
            if a[0] < b[0]:
                x, y = a
                x_end = b[0]
            else:
                x, y = b
                x_end = a[0]

            # fill in the first point
            line[x, y] = 1

            while x < x_end:

                # next points to try are
                poss_x = [x,      x,     x+1,   x+1,   x+1]
                poss_y = [y-1,    y+1,   y-1,   y,     y+1]

                # find the point closest to the line
                true_y = m * poss_x + c
                diff = (poss_y - true_y)**2
                index = matlab_find(diff == min(diff))[0]

                # the next point
                x = poss_x[index[0] - 1]
                y = poss_y[index[0] - 1]

                # add the point to the line
                line[x - 1, y - 1] = 1

        elif not np.isinf(abs(m)):

            # start at the end with the smallest value of y
            if a[1] < b[1]:
                x = a[0]
                y = a[1]
                y_end = b[1]
            else:
                x = b[0]
                y = b[1]
                y_end = a[1]

            # fill in the first point
            line[x, y] = 1

            while y < y_end:

                # next points to try are
                poss_y = [y,   y,   y+1,   y+1, y+1]
                poss_x = [x-1, x+1, x-1,   x,   x+1]

                # find the point closest to the line
                true_x = (poss_y - c) / m
                diff = (poss_x - true_x)**2
                index = matlab_find(diff == min(diff))[0]

                # the next point
                x = poss_x[index[0] - 1]
                y = poss_y[index[0] - 1]

                # add the point to the line
                line[x, y] = 1

        else: # m = +-Inf

            # start at the end with the smallest value of y
            if a[1] < b[1]:
                x = a[0]
                y = a[1]
                y_end = b[1]
            else:
                x = b[0]
                y = b[1]
                y_end = a[1]

            # fill in the first point
            line[x, y] = 1

            while y < y_end:

                # next point
                y = y + 1

                # add the point to the line
                line[x, y] = 1

    # =========================================================================
    # CALCULATE AN ANGLED LINE
    # =========================================================================

    elif linetype == 'angled':

        # define an empty grid to hold the line
        line = np.zeros((Nx, Ny))

        # start at the atart
        x, y = startpoint

        # fill in the first point
        line[x - 1, y - 1] = 1

        # initialise the current length of the line
        line_length = 0

        if abs(angle) == np.pi:

            while line_length < linelength:

                # next point
                y = y + 1

                # stop the points incrementing at the edges
                if y > Ny:
                    break

                # add the point to the line
                line[x - 1, y - 1] = 1

                # calculate the current length of the line
                line_length = np.sqrt((x - startpoint[0])**2 + (y - startpoint[1])**2)

        elif (angle < np.pi) and (angle > np.pi/2):

            # define the equation of the line
            m = -np.tan(angle - np.pi/2)   # gradient of the line
            c = y - m * x            # where the line crosses the y axis

            while line_length < linelength:

                # next points to try are
                poss_x = np.array([x-1, x-1, x  ])
                poss_y = np.array([y,   y+1, y+1])

                # find the point closest to the line
                true_y = m * poss_x + c
                diff = (poss_y - true_y)**2
                index = matlab_find(diff == min(diff))[0]

                # the next point
                x = poss_x[index[0] - 1]
                y = poss_y[index[0] - 1]

                # stop the points incrementing at the edges
                if (x < 0) or (y > Ny - 1):
                    break

                # add the point to the line
                line[x - 1, y - 1] = 1

                # calculate the current length of the line
                line_length = np.sqrt((x - startpoint[0])**2 + (y - startpoint[1])**2)

        elif angle == np.pi/2:

            while line_length < linelength:

                # next point
                x = x - 1

                # stop the points incrementing at the edges
                if x < 1:
                    break

                # add the point to the line
                line[x - 1, y - 1] = 1

                # calculate the current length of the line
                line_length = np.sqrt((x - startpoint[0])**2 + (y - startpoint[1])**2)

        elif (angle < np.pi/2) and (angle > 0):

            # define the equation of the line
            m = np.tan(np.pi/2 - angle)    # gradient of the line
            c = y - m * x            # where the line crosses the y axis

            while line_length < linelength:

                # next points to try are
                poss_x = np.array([x-1, x-1, x ])
                poss_y = np.array([y,   y-1, y-1])

                # find the point closest to the line
                true_y = m * poss_x + c
                diff = (poss_y - true_y)**2
                index = matlab_find(diff == min(diff))[0]

                # the next point
                x = poss_x[index[0] - 1]
                y = poss_y[index[0] - 1]

                # stop the points incrementing at the edges
                if (x < 1) or (y < 1):
                    break

                # add the point to the line
                line[x - 1, y - 1] = 1

                # calculate the current length of the line
                line_length = np.sqrt((x - startpoint[0])**2 + (y - startpoint[1])**2)

        elif angle==0:

            while line_length < linelength:

                # next point
                y = y - 1

                # stop the points incrementing at the edges
                if y < 1:
                    break

                # add the point to the line
                line[x - 1, y - 1] = 1

                # calculate the current length of the line
                line_length = np.sqrt((x - startpoint[0])**2 + (y - startpoint[1])**2)

        elif (angle < 0) and (angle > -np.pi/2):

            # define the equation of the line
            m = -np.tan(np.pi/2 + angle)   # gradient of the line
            c = y - m * x            # where the line crosses the y axis

            while line_length < linelength:

                # next points to try are
                poss_x = np.array([x+1, x+1, x ])
                poss_y = np.array([y,   y-1, y-1])

                # find the point closest to the line
                true_y = m * poss_x + c
                diff = (poss_y - true_y)**2
                index = matlab_find(diff == min(diff))[0]

                # the next point
                x = poss_x[index[0] - 1]
                y = poss_y[index[0] - 1]

                # stop the points incrementing at the edges
                if (x > Nx) or (y < 1):
                    break

                # add the point to the line
                line[x - 1, y - 1] = 1

                # calculate the current length of the line
                line_length = np.sqrt((x - startpoint[0])**2 + (y - startpoint[1])**2)

        elif angle == -np.pi/2:

            while line_length < linelength:

                # next point
                x = x + 1

                # stop the points incrementing at the edges
                if x > Nx:
                    break

                # add the point to the line
                line[x - 1, y - 1] = 1

                # calculate the current length of the line
                line_length = np.sqrt((x - startpoint[0])**2 + (y - startpoint[1])**2)

        elif (angle < -np.pi/2) and (angle > -np.pi):

            # define the equation of the line
            m = np.tan(-angle - np.pi/2)     # gradient of the line
            c = y - m * x              # where the line crosses the y axis

            while line_length < linelength:

                # next points to try are
                poss_x = np.array([x+1, x+1,  x ])
                poss_y = np.array([y,   y+1, y+1])

                # find the point closest to the line
                true_y = m * poss_x + c
                diff = (poss_y - true_y)**2
                index = matlab_find(diff == min(diff))[0]

                # the next point
                x = poss_x[index[0] - 1]
                y = poss_y[index[0] - 1]

                # stop the points incrementing at the edges
                if (x > Nx) or (y > Ny):
                    break

                # add the point to the line
                line[x - 1, y - 1] = 1

                # calculate the current length of the line
                line_length = np.sqrt((x - startpoint[0])**2 + (y - startpoint[1])**2)

    return line


def makeArc(grid_size: np.ndarray, arc_pos: np.ndarray, radius, diameter, focus_pos: np.ndarray):
    # force integer input values
    grid_size = grid_size.round().astype(int)
    arc_pos   = arc_pos.round().astype(int)
    diameter  = int(round(diameter))
    focus_pos = focus_pos.round().astype(int)

    try:
        radius = int(radius)
    except OverflowError:
        radius = float(radius)

    # check the input ranges
    if np.any(grid_size < 1):
        raise ValueError('The grid size must be positive.')
    if radius <= 0:
        raise ValueError('The radius must be positive.')

    if diameter <= 0:
        raise ValueError('The diameter must be positive.')

    if np.any(arc_pos < 1) or np.any(arc_pos > grid_size):
        raise ValueError('The centre of the arc must be within the grid.')

    if diameter > 2 * radius:
        raise ValueError('The diameter of the arc must be less than twice the radius of curvature.')

    if diameter % 2 != 1:
        raise ValueError('The diameter must be an odd number of grid points.')

    if np.all(arc_pos == focus_pos):
        raise ValueError('The focus_pos must be different to the arc_pos.')

    # assign variable names to vector components
    Nx, Ny = grid_size
    ax, ay = arc_pos
    fx, fy = focus_pos

    # =========================================================================
    # CREATE ARC
    # =========================================================================

    if not np.isinf(radius):

        # find half the arc angle
        half_arc_angle = np.arcsin(diameter / 2 / radius)

        # find centre of circle on which the arc lies
        distance_cf = np.sqrt( (ax - fx)**2 + (ay - fy)**2 )
        cx = round(radius / distance_cf * (fx - ax) + ax)
        cy = round(radius / distance_cf * (fy - ay) + ay)
        c = np.array([cx, cy])

        # create circle
        arc = makeCircle(Nx, Ny, cx, cy, radius)

        # form vector from the geometric arc centre to the arc midpoint
        v1 = arc_pos - c

        # calculate length of vector
        l1 = np.sqrt(sum((arc_pos - c)**2))

        # extract all points that form part of the arc
        arc_ind = matlab_find(arc, mode='eq', val=1)

        # loop through the arc points
        for arc_ind_i in arc_ind:

            # extract the indices of the current point
            x_ind, y_ind = ind2sub([Nx, Ny], arc_ind_i)
            p = np.array([x_ind, y_ind])

            # form vector from the geometric arc centre to the current point
            v2 = p - c

            # calculate length of vector
            l2 = np.sqrt(sum((p - c)**2))

            # find the angle between the two vectors using the dot product,
            # normalised using the vector lengths
            theta = np.arccos(sum( v1 * v2 / (l1 * l2) ))

            # if the angle is greater than the half angle of the arc, remove
            # it from the arc
            if theta > half_arc_angle:
                arc[x_ind - 1, y_ind - 1] = 0   # FARID NOTE: Possibly won't work due to indexing differences
    else:

        # calculate arc direction angle, then rotate by 90 degrees
        ang = np.arctan( (fx - ax) / (fy - ay) ) + np.pi/2

        # draw lines to create arc with infinite radius
        arc = np.logical_or(
            makeLine(Nx, Ny, arc_pos, endpoint=None, angle=ang, length=(diameter - 1)//2),
            makeLine(Nx, Ny, arc_pos, endpoint=None, angle=(ang + np.pi), length=(diameter - 1)//2)
        )
    return arc


def ind2sub(array_shape, ind):
    # Matlab style ind2sub
    row, col = np.unravel_index(ind - 1, array_shape, order='F')
    return row[0] + 1, col[0] + 1
