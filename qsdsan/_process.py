# -*- coding: utf-8 -*-
'''
QSDsan: Quantitative Sustainable Design for sanitation and resource recovery systems
Copyright (C) 2020, Quantitative Sustainable Design Group

This module is developed by:
    Joy Cheung <joycheung1994@gmail.com>

This module is under the UIUC open-source license. Please refer to 
https://github.com/QSD-Group/QSDsan/blob/master/LICENSE.txt
for license details.
'''

# import thermosteam as tmo
from _parse import get_stoichiometric_coeff
from thermosteam.utils import chemicals_user
from sympy import symbols, Matrix
from sympy.parsing.sympy_parser import parse_expr
import numpy as np
    
__all__ = ('Process',)

#%%
@chemicals_user        
class Process():
    
    def __init__(self, reaction, ref_component, rate_equation=None, components=None, 
                 conserved_for=('COD', 'N', 'P', 'charge'), parameters=None):
        
        self._stoichiometry = []
        self._components = self._load_chemicals(components)
        self._ref_component = ref_component
        self._conserved_for = conserved_for
        self._parameters = {p: symbols(p) for p in parameters}
        
        self._stoichiometry = get_stoichiometric_coeff(reaction, self._ref_component, self._components, self._conserved_for, self._parameters)
        self._parse_rate_eq(rate_equation)
                
    def get_conversion_factors(self, as_matrix=False):        
        '''
        return conversion factors as a numpy ndarray to check conservation
        or return them as a sympy matrix to solve for unknown stoichiometric coefficients.
        '''
        if self._conservation_for:
            cmps = self._components
            arr = getattr(cmps, 'i_'+self._conservation_for[0])
            for c in self._conservation_for[1:]:
                arr = np.vstack((arr, getattr(cmps, 'i_'+c)))
            if as_matrix: return Matrix(arr.tolist())
            return arr
        else: return None
                    
    def check_conservation(self, tol=1e-8):
        '''check conservation for given tuple of materials subject to conservation. '''
        isa = isinstance
        if isa(self._stoichiometry, np.ndarray):
            ic = self.get_conversion_factors()
            v = self._stoichiometry
            ic_dot_v = ic @ v
            conserved_arr = np.isclose(ic_dot_v, np.zeros(ic_dot_v.shape), atol=tol)
            if not conserved_arr.all(): 
                materials = self._conserved_for
                unconserved = [(materials[i], ic_dot_v[i]) for i, conserved in enumerate(conserved_arr) if not conserved]
                raise RuntimeError("The following materials are unconserved by the "
                                   "stoichiometric coefficients. A positive value "
                                   "means the material is created, a negative value "
                                   "means the material is destroyed:\n "
                                   + "\n ".join([f"{material}: {value:.2f}" for material, value in unconserved]))
        else: 
            raise RuntimeError("Can only check conservations with numerical "
                               "stoichiometric coefficients.")
    
    def reverse(self):
        '''reverse the process as to flip the signs of all components.'''
        if isinstance(self._stoichiometry, np.ndarray):
            self._stoichiometry = -self._stoichiometry
        else:
            self._stoichiometry = [-v for v in self._stoichiometry]
        self._rate_equation = -self._rate_equation
        
    @property
    def ref_component(self):
        return getattr(self._components, self._ref_component)    
    @ref_component.setter
    def ref_component(self, ref_cmp):
        if ref_cmp: 
            self._ref_component = ref_cmp
            self._normalize_stoichiometry(ref_cmp)
            self._normalize_rate_eq(ref_cmp)

    @property
    def conserved_for(self):
        return self._conserved_for
    @conserved_for.setter
    def conserved_for(self, materials):
        self._conserved_for = materials
    
    @property
    def parameters(self):
        return sorted(self._parameters)
    
    def append_parameters(self, *new_pars):
        for p in new_pars:
            self._parameters[p] = symbols(p)
    
    #TODO: set parameter values (and evaluate coefficients and rate??)
    def set_parameters(self):
        pass
    
    #!!! only show non-zero coefficients
    @property
    def stoichiometry(self):
        allcmps = dict(zip(self._components.IDs, self._stoichiometry))
        return {k:v for k,v in allcmps.items() if v != 0}
        
    @property
    def rate_equation(self):
        return self._rate_equation
    
    def _parse_rate_eq(self, eq):
        cmpconc_symbols = {c: symbols(c) for c in self._components.IDs}
        self._rate_equation = parse_expr(eq, {**cmpconc_symbols, **self._parameters})
    
    def _normalize_stoichiometry(self, new_ref):
        isa = isinstance
        factor = abs(self._stoichiometry[self._components._index[new_ref]])
        if isa(self._stoichiometry, np.ndarray):
            self._stoichiometry /= factor
        elif isa(self._stoichiometry, list):
            self._stoichiometry = [v/factor for v in self._stoichiometry]
    
    def _normalize_rate_eq(self, new_ref):
        factor = self._stoichiometry[self._components._index[new_ref]]
        self._rate_equation *= factor
