"""
The refdata module contains pure-element reference state data.
"""

from collections import OrderedDict
import json
import importlib.resources as impresources
from libreCalphad.models.energy import create_espei_custom_refstate_stable
import os
from pycalphad import variables as v
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
                    (se.Symbol(value), se.And(v.T < 10000.0, v.T > 1e-5)),
                    (0, True),
                )
        else:
            LCRefState[(element, phase)] = create_espei_custom_refstate_stable(value)
for key, value in list(ser_dict.items()):
    LCRefStateSER[key] = value
