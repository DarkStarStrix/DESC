import numpy as np
from scipy.optimize import fsolve
from netCDF4 import Dataset

from desc.backend import sign
from desc.zernike import ZernikeTransform, double_fourier_basis


# TODO: add other fields including B, rmns, zmnc, lmnc, etc
def read_vmec_output(fname):
    """Reads VMEC data from wout nc file

    Parameters
    ----------
    fname : str or path-like
        filename of VMEC output file

    Returns
    -------
    vmec_data : dict
        the VMEC data fields

    """

    file = Dataset(fname, mode='r')

    vmec_data = {
        'NFP': file.variables['nfp'][:],
        'psi': file.variables['phi'][:],  # toroidal flux is saved as 'phi'
        'xm': file.variables['xm'][:],
        'xn': file.variables['xn'][:],
        'rmnc': file.variables['rmnc'][:],
        'zmns': file.variables['zmns'][:],
        'lmns': file.variables['lmns'][:]
    }
    try:
        vmec_data['rmns'] = file.variables['rmns'][:]
        vmec_data['zmnc'] = file.variables['zmnc'][:]
        vmec_data['lmnc'] = file.variables['lmnc'][:]
        vmec_data['sym'] = False
    except:
        vmec_data['sym'] = True

    return vmec_data


def convert_vmec_to_desc(vmec_data, zern_idx, lambda_idx, Npol=None, Ntor=None):
    """Computes error in SFL coordinates compared to VMEC solution

    Parameters
    ----------

    vmec_data : dict
        dictionary of VMEC equilibrium parameters
    zern_idx : ndarray, shape(N_coeffs,3)
        indices for R,Z spectral basis,
        ie an array of [l,m,n] for each spectral coefficient
    lambda_idx : ndarray, shape(2M+1)*(2N+1)
        indices for lambda spectral basis,
        ie an array of [m,n] for each spectral coefficient
    Npol : int
        number of poloidal angles to sample per surface (Default value = M)
    Ntor : int
        number of toroidal angles to sample per surface (Default value = N)

    Returns
    -------
    equil : dict
        dictionary of DESC equilibrium parameters

    """

    if Npol is None:
        Npol = 2*np.max(zern_idx[:,1]) + 1
    if Ntor is None:
        Ntor = 2*np.max(zern_idx[:,2]) + 1

    ns = np.size(vmec_data['psi'])
    vartheta = np.linspace(0, 2*np.pi, Npol, endpoint=False)
    zeta = np.linspace(0, 2*np.pi/vmec_data['NFP'], Ntor, endpoint=False)
    phi = zeta

    r = np.tile(np.sqrt(vmec_data['psi'])[..., np.newaxis, np.newaxis], (1, Npol, Ntor))
    v = np.tile(vartheta[np.newaxis, ..., np.newaxis], (ns, 1, Ntor))
    z = np.tile(zeta[np.newaxis, np.newaxis, ...], (ns, Npol, 1))

    nodes = np.stack([r.flatten(), v.flatten(), z.flatten()])
    zernike_transform = ZernikeTransform(
        nodes, zern_idx, vmec_data['NFP'], method='fft')
    four_bdry_interp = double_fourier_basis(v[0,:,:].flatten(), z[0,:,:].flatten(), lambda_idx[:,0], lambda_idx[:,1], vmec_data['NFP'])
    four_bdry_interp_pinv = np.linalg.pinv(four_bdry_interp, rcond=1e-6)

    print('Interpolating VMEC solution to sfl coordinates')
    R = np.zeros((ns, Npol, Ntor))
    Z = np.zeros((ns, Npol, Ntor))
    L = np.zeros((Npol, Ntor))
    for k in range(Ntor):           # toroidal angle
        for i in range(ns):         # flux surface
            theta = np.zeros((Npol,))
            for j in range(Npol):   # poloidal angle
                f0 = sfl_err(np.array([0]), vartheta[j], zeta[k], vmec_data, i)
                f2pi = sfl_err(np.array([2*np.pi]),
                               vartheta[j], zeta[k], vmec_data, i)
                flag = (sign(f0) + sign(f2pi)) / 2
                args = (vartheta[j], zeta[k], vmec_data, i, flag)
                t = fsolve(sfl_err, vartheta[j], args=args)
                if flag != 0:
                    t = np.remainder(t+np.pi, 2*np.pi)
                theta[j] = t   # theta angle that corresponds to vartheta[j]
            R[i, :, k] = vmec_transf(
                vmec_data['rmnc'][i, :], vmec_data['xm'], vmec_data['xn'], theta, phi[k], trig='cos').flatten()
            Z[i, :, k] = vmec_transf(
                vmec_data['zmns'][i, :], vmec_data['xm'], vmec_data['xn'], theta, phi[k], trig='sin').flatten()
            if i == ns-1:
                L[:, k] = vmec_transf(
                    vmec_data['lmns'][i, :], vmec_data['xm'], vmec_data['xn'], theta, phi[k], trig='sin').flatten()
            if not vmec_data['sym']:
                R[i, :, k] += vmec_transf(vmec_data['rmns'][i, :], vmec_data['xm'],
                                          vmec_data['xn'], theta, phi[k], trig='sin').flatten()
                Z[i, :, k] += vmec_transf(vmec_data['zmnc'][i, :], vmec_data['xm'],
                                          vmec_data['xn'], theta, phi[k], trig='cos').flatten()
                if i == ns-1:
                    L[:, k] += vmec_transf(vmec_data['lmnc'][i, :], vmec_data['xm'],
                                           vmec_data['xn'], theta, phi[k], trig='cos').flatten()
        print('{}%'.format((k+1)/Ntor*100))

    cR = zernike_transform.fit(R.flatten())
    cZ = zernike_transform.fit(Z.flatten())
    cL = np.matmul(four_bdry_interp_pinv, L)
    equil = {
        'cR': cR,
        'cZ': cZ,
        'cL': cL,
        'bdryR': None,
        'bdryZ': None,
        'cP': None,
        'cI': None,
        'Psi_lcfs': vmec_data['psi'],
        'NFP': vmec_data['NFP'],
        'zern_idx': zern_idx,
        'lambda_idx': lambda_idx,
        'bdry_idx': None
    }
    return equil


def vmec_error(equil, vmec_data, Npol=8, Ntor=8):
    """Computes error in SFL coordinates compared to VMEC solution

    Parameters
    ----------
    equil : dict
        dictionary of DESC equilibrium parameters
    vmec_data : dict
        dictionary of VMEC equilibrium parameters
    Npol : int
        number of poloidal angles to sample per surface (Default value = 8)
    Ntor : int
        number of toroidal angles to sample per surface (Default value = 8)

    Returns
    -------
    err : float
        average Euclidean distance between VMEC and DESC sample points

    """

    ns = np.size(vmec_data['psi'])
    vartheta = np.linspace(0, 2*np.pi, Npol, endpoint=False)
    zeta = np.linspace(0, 2*np.pi/vmec_data['NFP'], Ntor, endpoint=False)
    phi = zeta

    r = np.tile(np.sqrt(vmec_data['psi'])
                [..., np.newaxis, np.newaxis], (1, Npol, Ntor))
    v = np.tile(vartheta[np.newaxis, ..., np.newaxis], (ns, 1, Ntor))
    z = np.tile(zeta[np.newaxis, np.newaxis, ...], (ns, Npol, 1))
    nodes = np.stack([r.flatten(), v.flatten(), z.flatten()])
    zernike_transform = ZernikeTransform(
        nodes, equil['zern_idx'], equil['NFP'], method='fft')
    R_desc = zernike_transform.transform(
        equil['cR'], 0, 0, 0).reshape((ns, Npol, Ntor))
    Z_desc = zernike_transform.transform(
        equil['cZ'], 0, 0, 0).reshape((ns, Npol, Ntor))

    print('Interpolating VMEC solution to sfl coordinates')
    R_vmec = np.zeros((ns, Npol, Ntor))
    Z_vmec = np.zeros((ns, Npol, Ntor))
    for k in range(Ntor):           # toroidal angle
        for i in range(ns):         # flux surface
            theta = np.zeros((Npol,))
            for j in range(Npol):   # poloidal angle
                f0 = sfl_err(np.array([0]), vartheta[j], zeta[k], vmec_data, i)
                f2pi = sfl_err(np.array([2*np.pi]),
                               vartheta[j], zeta[k], vmec_data, i)
                flag = (sign(f0) + sign(f2pi)) / 2
                args = (vartheta[j], zeta[k], vmec_data, i, flag)
                t = fsolve(sfl_err, vartheta[j], args=args)
                if flag != 0:
                    t = np.remainder(t+np.pi, 2*np.pi)
                theta[j] = t   # theta angle that corresponds to vartheta[j]
            R_vmec[i, :, k] = vmec_transf(
                vmec_data['rmnc'][i, :], vmec_data['xm'], vmec_data['xn'], theta, phi[k], trig='cos').flatten()
            Z_vmec[i, :, k] = vmec_transf(
                vmec_data['zmns'][i, :], vmec_data['xm'], vmec_data['xn'], theta, phi[k], trig='sin').flatten()
            if not vmec_data['sym']:
                R_vmec[i, :, k] += vmec_transf(vmec_data['rmns'][i, :], vmec_data['xm'],
                                               vmec_data['xn'], theta, phi[k], trig='sin').flatten()
                Z_vmec[i, :, k] += vmec_transf(vmec_data['zmnc'][i, :], vmec_data['xm'],
                                               vmec_data['xn'], theta, phi[k], trig='cos').flatten()
        print('{}%'.format((k+1)/Ntor*100))

    return np.mean(np.sqrt((R_vmec - R_desc)**2 + (Z_vmec - Z_desc)**2))


def sfl_err(theta, vartheta, zeta, vmec_data, s, flag=0):
    """f(theta) = vartheta - theta - lambda(theta)

    Parameters
    ----------
    theta : float
        VMEC poloidal angle
    vartheta : float
        sfl poloidal angle
    zeta : float
        VMEC/sfl toroidal angle
    vmec_data : dict
        dictionary of VMEC equilibrium parameters
    flag : int
        offsets theta to ensure f(theta) has one zero (Default value = 0)
    s :


    Returns
    -------
    err : float
        vartheta - theta - lambda

    """

    theta = theta[0] + np.pi*flag
    phi = zeta
    l = vmec_transf(vmec_data['lmns'][s, :], vmec_data['xm'],
                    vmec_data['xn'], theta, phi, trig='sin')
    if not vmec_data['sym']:
        l += vmec_transf(vmec_data['lmnc'][s, :], vmec_data['xm'],
                         vmec_data['xn'], theta, phi, trig='cos')
    return vartheta - theta - l[0][0][0]


def vmec_transf(xmna, xm, xn, theta, phi, trig='sin'):
    """Compute Fourier transform of VMEC data

    Parameters
    ----------
    xmns : 2d float array
        xmnc[:,i] are the sin coefficients at flux surface i
    xm : 1d int array
        poloidal mode numbers
    xn : 1d int array
        toroidal mode numbers
    theta : 1d float array
        poloidal angles
    phi : 1d float array
        toroidal angles
    trig : string
        type of transform, options are 'sin' or 'cos' (Default value = 'sin')
    xmna :


    Returns
    -------
    f : ndarray
        f[i,j,k] is the transformed data at flux surface i, theta[j], phi[k]

    """

    ns = np.shape(np.atleast_2d(xmna))[0]
    lt = np.size(theta)
    lp = np.size(phi)
    # Create mode x angle arrays
    mtheta = np.atleast_2d(xm).T @ np.atleast_2d(theta)
    nphi = np.atleast_2d(xn).T @ np.atleast_2d(phi)
    # Create trig arrays
    cosmt = np.cos(mtheta)
    sinmt = np.sin(mtheta)
    cosnp = np.cos(nphi)
    sinnp = np.sin(nphi)
    # Calcualte the transform
    f = np.zeros((ns, lt, lp))
    for k in range(ns):
        xmn = np.tile(np.atleast_2d(np.atleast_2d(xmna)[k, :]).T, (1, lt))
        if trig == 'sin':
            f[k, :, :] = np.tensordot(
                (xmn*sinmt).T, cosnp, axes=1) + np.tensordot((xmn*cosmt).T, sinnp, axes=1)
        elif trig == 'cos':
            f[k, :, :] = np.tensordot(
                (xmn*cosmt).T, cosnp, axes=1) - np.tensordot((xmn*sinmt).T, sinnp, axes=1)
    return f


# TODO: replace this function with vmec_transf
def vmec_interpolate(Cmn, Smn, xm, xn, theta, phi, sym=True):
    """Interpolates VMEC data on a flux surface

    Parameters
    ----------
    Cmn : ndarray
        cos(mt-np) Fourier coefficients
    Smn : ndarray
        sin(mt-np) Fourier coefficients
    xm : ndarray
        poloidal mode numbers
    xn : ndarray
        toroidal mode numbers
    theta : ndarray
        poloidal angles
    phi : ndarray
        toroidal angles
    sym : bool
        stellarator symmetry (Default value = True)

    Returns
    -------
    if sym = True
        C, S (tuple of ndarray): VMEC data interpolated at the angles (theta,phi)
        where C has cosine symmetry and S has sine symmetry
    if sym = False
        X (ndarray): non-symmetric VMEC data interpolated at the angles (theta,phi)

    """

    C_arr = []
    S_arr = []
    dim = Cmn.shape

    for j in range(dim[1]):

        m = xm[j]
        n = xn[j]

        C = [[[Cmn[s, j]*np.cos(m*t - n*p) for p in phi]
              for t in theta] for s in range(dim[0])]
        S = [[[Smn[s, j]*np.sin(m*t - n*p) for p in phi]
              for t in theta] for s in range(dim[0])]
        C_arr.append(C)
        S_arr.append(S)

    C = np.sum(C_arr, axis=0)
    S = np.sum(S_arr, axis=0)
    if sym:
        return C, S
    else:
        return C + S
