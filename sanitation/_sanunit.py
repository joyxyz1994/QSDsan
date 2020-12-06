#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Sanitation Explorer: Sustainable design of non-sewered sanitation technologies
Copyright (C) 2020, Sanitation Explorer Development Group

This module is developed by:
    Yalin Li <zoe.yalin.li@gmail.com>

This module is under the UIUC open-source license. Please refer to 
https://github.com/QSD-for-WaSH/sanitation/blob/master/LICENSE.txt
for license details.

'''


# %%

import biosteam as bst
from biosteam import utils
from . import currency, Construction, Transportation
from .utils.piping import WSIns, WSOuts


__all__ = ('SanUnit',)

@utils.registered(ticket_name='SU')
class SanUnit(bst.Unit, isabstract=True):

    '''
    Subclass of Unit in biosteam, is initialized with WasteStream rather than Stream.
    
    Additional attributes
    --------------------
    construction : [tuple]
        Contains construction information.
    construction_impacts : [dict]
        Total impacts associated with this SanUnit.
    transportation : [tuple]
        Contains construction information.
    add_OPEX : [float]
        Operating expense per hour in addition to utility cost (assuming 100% uptime).
    uptime_ratio : [float]
        Uptime of the unit to adjust add_OPEX, should be in [0,1] (i.e., a unit that is always operating).
    
    biosteam document
    -----------------

    '''
    
    _stacklevel = 7

    def __init__(self, ID='', ins=None, outs=(), thermo=None):
        self._register(ID)
        self._specification = None
        self._load_thermo(thermo)
        self._init_ins(ins)
        self._init_outs(outs)
        self._init_utils()
        self._init_results()
        self._assert_compatible_property_package()
        self._add_OPEX = 0.
        self._uptime_ratio = 1.

    __doc__ += bst.Unit.__doc__
    __init__.__doc__ = __doc__    


    def _init_ins(self, ins):
        self._ins = WSIns(self, self._N_ins, ins, self._thermo,
                          self._ins_size_is_fixed, self._stacklevel)
        
    def _init_outs(self, outs):
        self._outs = WSOuts(self, self._N_outs, outs, self._thermo,
                            self._outs_size_is_fixed, self._stacklevel)

    def _init_results(self):
        super()._init_results()
        self._construction = ()
        self._transportation = ()

    def _info(self, T, P, flow, composition, N, _stream_info):
        """Information of the unit."""
        if self.ID:
            info = f'{type(self).__name__}: {self.ID}\n'
        else:
            info = f'{type(self).__name__}\n'
        info += 'ins...\n'
        i = 0
        for stream in self.ins:
            if not stream:
                info += f'[{i}] {stream}\n'
                i += 1
                continue
            if _stream_info:
                stream_info = stream._info(T, P, flow, composition, N) + \
                    '\n' + stream._wastestream_info()
            else:
                stream_info = stream._wastestream_info()
            unit = stream._source
            index = stream_info.index('\n')
            source_info = f'  from  {type(unit).__name__}-{unit}\n' if unit else '\n'
            info += f'[{i}] {stream.ID}' + source_info + stream_info[index+1:] + '\n'
            i += 1
        info += 'outs...\n'
        i = 0
        for stream in self.outs:
            if not stream:
                info += f'[{i}] {stream}\n'
                i += 1
                continue
            if _stream_info:
                stream_info = stream._info(T, P, flow, composition, N) + \
                    '\n' + stream._wastestream_info()
            else:
                stream_info = stream._wastestream_info()
            unit = stream._sink
            index = stream_info.index('\n')
            sink_info = f'  to  {type(unit).__name__}-{unit}\n' if unit else '\n'
            info += f'[{i}] {stream.ID}' + sink_info + stream_info[index+1:] + '\n'
            i += 1
        info = info.replace('\n ', '\n    ')
        return info[:-1]
    
    
    _impact = utils.NotImplementedMethod


    def _summary(self):
        '''After system converges, design unit and calculate cost and environmental impacts'''
        self._design()
        self._cost()
        self._impact()
    
    
    def show(self, T=None, P=None, flow='g/hr', composition=None, N=15, stream_info=True):
        """Print information of the unit, including WasteStream-specific information"""
        print(self._info(T, P, flow, composition, N, stream_info))
    
    def add_construction(self, add_unit=True, add_design=True, add_cost=True):
        '''Batch-adding construction unit, designs, and costs.'''
        for i in self.construction:
            if add_unit:
                self._units[i.item.ID] = i.item.functional_unit
            if add_design:
                self.design_results[i.item.ID] = i.quantity
            if add_cost:
                self.purchase_costs[i.item.ID] = i.cost
    
    @property
    def construction(self):
        '''[tuple] Contains construction information.'''
        return self._construction
    @construction.setter
    def construction(self, i):
        if isinstance(i, Construction):
            i = (i,)
        else:
            if not iter(i):
                raise TypeError(f'Only <Construction> can be included, not {type(i).__name__}.')
            for j in i:
                if not isinstance(j, Construction):
                    raise TypeError(f'Only <Construction> can be included, not {type(j).__name__}.')
        self._construction = i

    @property
    def construction_impacts(self):
        '''[dict] Total impacts associated with this SanUnit.'''
        impacts = {}
        if not self.construction:
            return impacts
        for i in self.construction:
            impact = i.impacts
            for i, j in impact.items():
                try: impacts[i] += j
                except: impacts[i] = j
        return impacts

    @property
    def transportation(self):
        '''[tuple] Contains transportation information.'''
        return self._transportation
    @transportation.setter
    def transportation(self, i):
        if isinstance(i, Transportation):
            i = (i,)
        else:
            if not iter(i):
                raise TypeError(f'Only <Transportation> can be included, not {type(i).__name__}.')
            for j in i:
                if not isinstance(j, Transportation):
                    raise TypeError(f'Only <Transportation> can be included, not {type(j).__name__}.')
        self._transportation = i

    @property
    def add_OPEX(self):
        '''[float] Operating expense per hour in addition to utility cost (assuming 100% operating time).'''
        return self._add_OPEX

    def results(self, with_units=True, include_utilities=True,
                include_total_cost=True, include_installed_cost=False,
                include_zeros=True, external_utilities=(), key_hook=None):
        results = super().results(with_units, include_utilities,
                                  include_total_cost, include_installed_cost,
                                  include_zeros, external_utilities, key_hook)
        if with_units:
            results.loc[('Additional OPEX', ''), :] = ('USD/hr', self.add_OPEX)
            results.replace({'USD': f'{currency}', 'USD/hr': f'{currency}/hr'}, inplace=True)
        else:
            results.loc[('Additional OPEX', ''), :] = self.add_OPEX
        return results

    @property
    def uptime_ratio(self):
        '''[float] Uptime of the unit to adjust add_OPEX, should be in [0,1] (i.e., a unit that is always operating).'''
        return self._uptime_ratio
    @uptime_ratio.setter
    def uptime_ratio(self, i):
        assert 0 <= i <= 1, f'Uptime must be between 0 and 1 (100%), not {i}.'
        self._uptime_ratio = float(i)













