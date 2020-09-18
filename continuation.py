import numpy as np
import scipy.optimize

from backend import jnp, jit, use_jax
from backend import get_needed_derivatives, unpack_x, jacfwd
from zernike import ZernikeTransform, get_zern_basis_idx_dense, get_double_four_basis_idx_dense, symmetric_x
from init_guess import get_initial_guess_scale_bdry
from boundary_conditions import format_bdry
from objective_funs import get_equil_obj_fun
from nodes import get_nodes_pattern


def expand_resolution(x,zernt,zern_idx_old,zern_idx_new,lambda_idx_old,lambda_idx_new,nodes_new=None):
    """Expands solution to a higher resolution by filling with zeros
    Also modifies zernike transform object to work at higher resolution
    
    Args:
        x (ndarray): solution at initial resolution
        zernt (ZernikeTransform): zernike transform object corresponding to initial x
        zern_idx_old (ndarray of int, size(nRZ_old,3)): mode indices corresponding to initial R,Z
        zern_idx_new (ndarray of int, size(nRZ_new,3)): mode indices corresponding to new R,Z
        lambda_idx_old (ndarray of int, size(nL_old,2)): mode indices corresponding to initial lambda
        lambda_idx_new (ndarray of int, size(nL_new,2)): mode indices corresponding to new lambda
        nodes_new (ndarray of float, size(Nn_new,3))(optional): new node locations
    Returns:
        x_new (ndarray): solution expanded to new resolution
    """
    
    cR,cZ,cL = unpack_x(x,len(zern_idx_old))
    cR_new = np.zeros(len(zern_idx_new))
    cZ_new = np.zeros(len(zern_idx_new))
    cL_new = np.zeros(len(lambda_idx_new))
    old_in_new = np.where((zern_idx_new[:, None] == zern_idx_old).all(-1))[0]
    cR_new[old_in_new] = cR
    cZ_new[old_in_new] = cZ
    old_in_new = np.where((lambda_idx_new[:, None] == lambda_idx_old).all(-1))[0]
    cL_new[old_in_new] = cL
    x_new = np.concatenate([cR_new,cZ_new,cL_new])
    
    if nodes_new is not None:
        zernt.expand_nodes(nodes_new)
    zernt.expand_spectral_resolution(zern_idx_new)
    
    return x_new, zernt


def perturb(x,equil_obj,delta_bdry,delta_pres,delta_zeta,delta_errr,args):
    """perturbs an equilibrium"""
    
    obj_jac  = jacfwd(equil_obj,argnums=0)
    Jx = obj_jac(x,*args)
    RHS = equil_obj(x,*args)
    
    if delta_bdry != 0:
        bdry_jac = jacfwd(equil_obj,argnums=6)
        Jb = bdry_jac(x,*args)
        RHS += Jb*delta_bdry
    if delta_bdry != 0:
        pres_jac = jacfwd(equil_obj,argnums=7)
        Jp = pres_jac(x,*args)
        RHS += Jp*delta_pres
    if delta_bdry != 0:
        zeta_jac = jacfwd(equil_obj,argnums=8)
        Jz = zeta_jac(x,*args)
        RHS += Jz*delta_zeta
    if delta_bdry != 0:
        errr_jac = jacfwd(equil_obj,argnums=9)
        Je = errr_jac(x,*args)
        RHS += Je*delta_errr
    
    dx = -np.linalg.lstsq(Jx,RHS,rcond=1e-6)[0]
    return x + dx


def solve_eq_continuation(inputs):
    """Solves for an equilibrium by continuation method
    
    Steps up resolution, perturbs pressure, 3d bdry etc.
    
    Args:
        inputs (dict): dictionary with input parameters defining problem setup and solver options
    
    Returns:
        equil (dict): dictionary of solution values
    """
    
    stell_sym  = inputs['stell_sym']
    NFP        = inputs['NFP']
    Psi_lcfs   = inputs['Psi_lcfs']
    M          = inputs['Mpol']       # arr
    N          = inputs['Ntor']       # arr
    Mnodes     = inputs['Mnodes']     # arr
    Nnodes     = inputs['Nnodes']     # arr
    bdry_ratio = inputs['bdry_ratio'] # arr
    pres_ratio = inputs['pres_ratio'] # arr
    zeta_ratio = inputs['zeta_ratio'] # arr
    errr_ratio = inputs['errr_ratio'] # arr
    ftol       = inputs['ftol']       # arr
    xtol       = inputs['xtol']       # arr
    gtol       = inputs['gtol']       # arr
    nfev       = inputs['nfev']       # arr
    verbose    = inputs['verbose']
    errr_mode  = inputs['errr_mode']
    bdry_mode  = inputs['bdry_mode']
    node_mode  = inputs['node_mode']
    out_fname  = inputs['out_fname']
    cP         = inputs['cP']
    cI         = inputs['cI']
    axis       = inputs['axis']
    bdry       = inputs['bdry']
    
    arr_len = M.size
    for ii in range(arr_len):
        
        if verbose > 0:
            print('================')
            print('Iteration {}/{}'.format(ii+1,arr_len))
            print('================')
            print('Spectral resolution (M,N)=({},{})'.format(M[ii],N[ii]))
            print('Node resolution (M,N)=({},{})'.format(Mnodes[ii],Nnodes[ii]))
            print('Boundary ratio = {}'.format(bdry_ratio[ii]))
            print('Pressure ratio = {}'.format(pres_ratio[ii]))
            print('Zeta ratio = {}'.format(zeta_ratio[ii]))
            print('Error ratio = {}'.format(errr_ratio[ii]))
            print('Function tolerance = {}'.format(ftol[ii]))
            print('Gradient tolerance = {}'.format(gtol[ii]))
            print('State vector tolerance = {}'.format(xtol[ii]))
            print('Max function evaluations = {}'.format(nfev[ii]))
            print('================')
        
        # initial solution
        if ii == 0:
            # interpolator
            if verbose > 0:
                print('Computing Fourier-Zernike basis')
            nodes,volumes = get_nodes_pattern(Mnodes[ii],Nnodes[ii],NFP,surfs=node_mode)
            derivatives = get_needed_derivatives('all')
            zern_idx = get_zern_basis_idx_dense(M[ii],N[ii])
            lambda_idx = get_double_four_basis_idx_dense(M[ii],N[ii])
            zernt = ZernikeTransform(nodes,zern_idx,NFP,derivatives)
            
            # format boundary shape
            bdry_pol,bdry_tor,bdryR,bdryZ = format_bdry(M[ii],N[ii],NFP,bdry,bdry_mode,bdry_mode)
            
            # stellarator symmetry
            if stell_sym:
                sym_mat = symmetric_x(M[ii],N[ii])
            else:
                sym_mat = np.eye(2*len(zern_idx) + len(lambda_idx))
            
            # initial guess
            if verbose > 0:
                print('Computing initial guess')
            cR_init,cZ_init = get_initial_guess_scale_bdry(axis,bdry,zern_idx,NFP,mode=bdry_mode,rcond=1e-6)
            cL_init = np.zeros(len(lambda_idx))
            x_init = jnp.concatenate([cR_init,cZ_init,cL_init])
            x_init = jnp.matmul(sym_mat.T,x_init)
            x = x_init
            equil_init = {
                'cR'         : cR_init,
                'cZ'         : cZ_init,
                'cL'         : cL_init,
                'bdryR'      : bdry[:,2],
                'bdryZ'      : bdry[:,3],
                'cP'         : cP,
                'cI'         : cI,
                'Psi_lcfs'   : Psi_lcfs,
                'NFP'        : NFP,
                'zern_idx'   : zern_idx,
                'lambda_idx' : lambda_idx,
                'bdry_idx'   : bdry[:,:2]
            }
            
            # equilibrium objective function
            equil_obj,callback = get_equil_obj_fun(stell_sym,errr_mode,bdry_mode,M[ii],N[ii],
                                 NFP,zernt,zern_idx,lambda_idx,bdry_pol,bdry_tor,nodes,volumes)
            args = [bdryR,bdryZ,cP,cI,Psi_lcfs,bdry_ratio[ii],pres_ratio[ii],zeta_ratio[ii],errr_ratio[ii]]
        
        # continuing from prev soln
        else:
            # spectral resolution
            if M[ii] != M[ii-1] or N[ii] != N[ii-1]:
                zern_idx_old = zern_idx
                lambda_idx_old = lambda_idx
                zern_idx = get_zern_basis_idx_dense(M[ii],N[ii])
                lambda_idx = get_double_four_basis_idx_dense(M[ii],N[ii])
                bdry_pol,bdry_tor,bdryR,bdryZ = format_bdry(M[ii],N[ii],NFP,bdry,bdry_mode,bdry_mode)
                
                x,zent = expand_resolution(jnp.matmul(sym_mat,x),zernt,zern_idx_old,zern_idx,lambda_idx_old,lambda_idx)
                if stell_sym:
                    sym_mat = symmetric_x(M[ii],N[ii])
                else:
                    sym_mat = np.eye(2*len(zern_idx) + len(lambda_idx))
                x = jnp.matmul(sym_mat.T,x)
            
            # collocation nodes
            if Mnodes[ii] != Mnodes[ii-1] or Nnodes[ii] != Nnodes[ii-1]:
                nodes,volumes = get_nodes_pattern(Mnodes[ii],Nnodes[ii],NFP,surfs=node_mode)
                zernt.expand_nodes(nodes)
            
            # continuation parameters
            delta_bdry = bdry_ratio[ii] - bdry_ratio[ii-1]
            delta_pres = pres_ratio[ii] - pres_ratio[ii-1]
            delta_zeta = zeta_ratio[ii] - zeta_ratio[ii-1]
            delta_errr = errr_ratio[ii] - errr_ratio[ii-1]
            
            # equilibrium objective function
            equil_obj,callback = get_equil_obj_fun(stell_sym,errr_mode,bdry_mode,M[ii],N[ii],
                                 NFP,zernt,zern_idx,lambda_idx,bdry_pol,bdry_tor,nodes,volumes)
            args = [bdryR,bdryZ,cP,cI,Psi_lcfs,bdry_ratio[ii],pres_ratio[ii],zeta_ratio[ii],errr_ratio[ii]]
            
            if use_jax:
                x = perturb(x,equil_obj,delta_bdry,delta_pres,delta_zeta,delta_errr,args)
        
        if use_jax:
            if verbose > 0:
                print('Compiling objective function')
            equil_obj_jit = jit(equil_obj,static_argnums=())
        else:
            equil_obj_jit = equil_obj
        if verbose > 0:
            print('Starting optimization')
        
        x_init = x
        out = scipy.optimize.least_squares(equil_obj_jit,
                                           x0=x_init,
                                           args=args,
                                           jac='2-point',
                                           method='trf',
                                           x_scale='jac',
                                           ftol=ftol[ii],
                                           xtol=xtol[ii],
                                           gtol=gtol[ii],
                                           max_nfev=nfev[ii],
                                           verbose=verbose)
        x = out['x']
        if verbose:
            print('Start of Iteration {}:'.format(ii+1))
            callback(x_init, *args)
            print('End of Iteration {}:'.format(ii+1))
            callback(x, *args)
        
        # TODO: checkpoint saving after each iteration
    
    cR,cZ,cL = unpack_x(np.matmul(sym_mat,x),len(zern_idx))
    equil = {
        'cR'         : cR,
        'cZ'         : cZ,
        'cL'         : cL,
        'bdryR'      : bdry[:,2],
        'bdryZ'      : bdry[:,3],
        'cP'         : cP,
        'cI'         : cI,
        'Psi_lcfs'   : Psi_lcfs,
        'NFP'        : NFP,
        'zern_idx'   : zern_idx,
        'lambda_idx' : lambda_idx,
        'bdry_idx'   : bdry[:,:2]
    }
    
    print('====================')
    print('Done')
    print('====================')
    # TODO: return the history of checkpoint solutions
    return equil_init, equil