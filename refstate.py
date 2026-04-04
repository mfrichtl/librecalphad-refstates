"""
The refdata module contains pure-element reference state data.
"""

from collections import OrderedDict
import json
import importlib.resources as impresources
from libreCalphad.models.segmented_regression import create_espei_custom_refstate_stable
import os
from pycalphad.variables import T
import symengine as se


def _shorten_sympy_floats(sympy_expression, precision=6):
    # Sympy defaults to representing numbers with too much precision for reflowing the text
    # to a TDB file. This function recurses through the Sympy terms and simplifies the
    # floats to reduce precision.
    recursed_args = []
    # print(sympy_expression)
    # print(type(sympy_expression))
    if isinstance(sympy_expression, se.Piecewise):
        # Assuming args alternate in expr, cond pairs:
        for i in range(len(sympy_expression.args) - 1):
            if i % 2 > 0:  # odd number should be a condition
                recursed_args.append(
                    (
                        _shorten_sympy_floats(sympy_expression.args[i - 1]),
                        sympy_expression.args[i],
                    )
                )
        print(sympy_expression)
        print(se.Piecewise(*recursed_args))
        return se.Piecewise(*recursed_args)
    elif isinstance(sympy_expression, se.Add):
        if len(sympy_expression.args) > 0:
            for arg in sympy_expression.args:
                recursed_args.append(_shorten_sympy_floats(arg))
            return se.Add(*recursed_args)
        else:
            return sympy_expression
    elif isinstance(sympy_expression, se.Mul):
        for arg in sympy_expression.args:
            recursed_args.append(_shorten_sympy_floats(arg))
        return se.Mul(*recursed_args)
    elif isinstance(sympy_expression, (se.Float, se.Integer, se.RealDouble)):
        return se.RealDouble(round(float(sympy_expression), precision))
    elif isinstance(sympy_expression, se.Rational):
        return se.RealDouble(round(float(sympy_expression), precision))
    elif isinstance(sympy_expression, se.Pow):
        if str(sympy_expression.args[0]) == "E":  # exp
            return se.exp(_shorten_sympy_floats(sympy_expression.args[1]))
        else:
            for arg in sympy_expression.args:
                recursed_args.append(_shorten_sympy_floats(arg))
            return se.Pow(*recursed_args)
    elif isinstance(sympy_expression, se.Symbol):
        return sympy_expression
    elif isinstance(sympy_expression, se.log):
        for arg in sympy_expression.args:
            recursed_args.append(_shorten_sympy_floats(arg))
        return se.log(*recursed_args)
    elif isinstance(sympy_expression, se.And):
        for arg in sympy_expression.args:
            recursed_args.append(_shorten_sympy_floats(arg))
        return se.And(*recursed_args)
    elif isinstance(sympy_expression, (se.StrictLessThan, se.LessThan)):
        return sympy_expression
    elif any([str(sympy_expression) == "True", str(sympy_expression) == "False"]):
        return sympy_expression
    else:
        raise NotImplementedError(
            f"Recurse function not implemented for {type(sympy_expression)}. File a complaint!"
        )


# Just hard code it in for now
_LCRefState_json = impresources.files("refstate") / "LCRefstates.json"
with open(_LCRefState_json, "r") as f:
    refstate_dict = json.load(f)
_LCSER_json = impresources.files("refstate") / "LCSERparams.json"
with open(_LCSER_json, "r") as f:
    ser_dict = json.load(f)

# # These are truncated versions of SGTE91. They are not correct and just here for an example.
# # These functions form GHSER<ELEMENT> names, e.g. GHERAG and GHSERAL, which are used in the lattice stabilities later.
LCRefStateStable = OrderedDict([])
LCRefState = OrderedDict([])
LCRefStateSER = OrderedDict([])
for key, value in list(refstate_dict.items()):
    if len(key.split("-")) == 1:
        # Should go into the stable dictionary
        LCRefStateStable[key] = create_espei_custom_refstate_stable(value)
    elif len(key.split("-")) == 2:
        # Lattice stability key
        element = key.split("-")[0]
        phase = key.split("-")[1]
        if isinstance(value, str):
            if value.startswith("GHSER"):
                LCRefState[(element, phase)] = se.Piecewise(
                    (se.Symbol(value), se.And(T < 10000.0, T > 1e-5)),
                    (0, True),
                )
        else:
            LCRefState[(element, phase)] = create_espei_custom_refstate_stable(value)
for key, value in list(ser_dict.items()):
    LCRefStateSER[key] = value

# This is the chemical potential relative to the standard state (reference structure, 1 mol, 298.15 K, 101325 Pa)
# The symbol GHSER[element] refers to an entry in SGTE above
# SGTE91[(element, reference structure)] = SGTE91Stable[element]
# Reference:
# A.T. Dinsdale, SGTE data for pure elements, Calphad, Volume 15, Issue 4, 1991, Pages 317-425, ISSN 0364-5916,
# http://dx.doi.org/10.1016/0364-5916(91)90030-N.
# http://www.sciencedirect.com/science/article/pii/036459169190030N
# LCRefState = OrderedDict(
#     [
#         (
#             ("AG", "BCC_A2"),
#             Piecewise(
#                 (3400 - 1.05 * T + Symbol("GHSERAG"), And(T < 3000.0, T >= 298.15)),
#                 evaluate=False,
#             ),
#         ),
#         (
#             ("AG", "CUB_A13"),
#             Piecewise(
#                 (3765.6 - 1.8826 * T + Symbol("GHSERAG"), And(T < 3000.0, T >= 298.15)),
#                 evaluate=False,
#             ),
#         ),
#         (
#             ("AG", "FCC_A1"),
#             Piecewise(
#                 (Symbol("GHSERAG"), And(T < 3000.0, T >= 298.15)), evaluate=False
#             ),
#         ),
#         (
#             ("AG", "HCP_A3"),
#             Piecewise(
#                 (300 + 0.3 * T + Symbol("GHSERAG"), And(T < 3000.0, T >= 298.15)),
#                 evaluate=False,
#             ),
#         ),
#         (
#             ("AG", "LIQUID"),
#             Piecewise(
#                 (
#                     11025.076 - 8.89102 * T - 1.033905e-20 * T**7 + Symbol("GHSERAG"),
#                     And(T < 1234.93, T >= 298.15),
#                 ),
#                 (
#                     -33.472 * T * log(T) + 180.964656 * T - 3587.111,
#                     And(T < 3000.0, T >= 1234.93),
#                 ),
#                 evaluate=False,
#             ),
#         ),
#         (
#             ("AL", "BCC_A2"),
#             Piecewise(
#                 (-4.813 * T + Symbol("GHSERAL") + 10083, And(T < 2900.0, T >= 298.15)),
#                 evaluate=False,
#             ),
#         ),
#         (
#             ("AL", "BCT_A5"),
#             Piecewise(
#                 (-4.813 * T + Symbol("GHSERAL") + 10083, And(T < 2900.0, T >= 298.15)),
#                 evaluate=False,
#             ),
#         ),
#         (
#             ("AL", "CBCC_A12"),
#             Piecewise(
#                 (
#                     -4.813 * T + Symbol("GHSERAL") + 10083.4,
#                     And(T < 2900.0, T >= 298.15),
#                 ),
#                 evaluate=False,
#             ),
#         ),
#         (
#             ("AL", "CUB_A13"),
#             Piecewise(
#                 (
#                     -4.8116 * T + Symbol("GHSERAL") + 10920.44,
#                     And(T < 2900.0, T >= 298.15),
#                 ),
#                 evaluate=False,
#             ),
#         ),
#         (
#             ("AL", "DIAMOND_A4"),
#             Piecewise(
#                 (30 * T + Symbol("GHSERAL"), And(T < 2900.0, T >= 298.15)),
#                 evaluate=False,
#             ),
#         ),
#         (
#             ("AL", "FCC_A1"),
#             Piecewise(
#                 (Symbol("GHSERAL"), And(T < 2900.0, T >= 298.15)), evaluate=False
#             ),
#         ),
#         (
#             ("AL", "HCP_A3"),
#             Piecewise(
#                 (-1.8 * T + Symbol("GHSERAL") + 5481, And(T < 2900.0, T >= 298.15)),
#                 evaluate=False,
#             ),
#         ),
#         (
#             ("AL", "LIQUID"),
#             Piecewise(
#                 (
#                     7.9337e-20 * T**7 - 11.841867 * T + Symbol("GHSERAL") + 11005.029,
#                     And(T < 700.0, T >= 298.15),
#                 ),
#                 (
#                     7.9337e-20 * T**7 - 11.841867 * T + Symbol("GHSERAL") + 11005.03,
#                     And(T < 933.47, T >= 700.0),
#                 ),
#                 (
#                     -31.748192 * T * log(T) + 177.430178 * T - 795.996,
#                     And(T < 2900.0, T >= 933.47),
#                 ),
#                 evaluate=False,
#             ),
#         ),
#     ]
# )
