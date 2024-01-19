
# Sample a program composed of RASP instructions:
# - Map
# - SequenceMap
# - LinearSequenceMap (compiled exactly into MLP weights)
# - Select
# - Aggregate
# - SelectorWidth


# Desiderata for sampled programs:
# - it follows the Tracr constraints so it compiles correctly
# - it has a reasonable number of instructions
# - it doesn't do anything trivial (eg return a constant)
# - it uses comparisons when appropriate (eg don't < compare two strings)


from tracr.rasp import rasp
import numpy as np
from tracr.compiler.validating import validate
from tracr.compiler import compiling
from rasp_generator import map_primitives, utils


class SamplingError(Exception):
    pass


TEST_INPUT = [1,2,3,4]  # used to validate programs


def sample_from_scope(
        rng: np.random.Generator,
        sops: list[rasp.SOp],
        type_constraint=None,
        other_constraints: list[callable] = [],
        size=None,
        replace=False,
    ):
    """Sample a SOp from a given list of SOps, according to constraints."""
    sops = utils.filter_by_type(sops, type=type_constraint)
    sops = utils.filter_by_constraints(sops, other_constraints)

    if size is not None and len(sops) < size:
        raise utils.EmptyScopeError(
            f"Not enough SOps in scope. Found {len(sops)}, need {size}")

    weights = [1] * len(sops)
    if type_constraint in {"categorical", None}:
        weights[0] = 3
    weights = np.array(weights) / np.sum(weights)

    return rng.choice(
        sops, 
        size=size, 
        replace=replace, 
        p=weights)


def sample_map(rng, variable_scope: list[rasp.SOp]):
    """Sample a map. A map applies a function elementwise to a SOp.
    The input SOps can be categorical, float, or bool."""
    sop_in = sample_from_scope(rng, variable_scope)
    fn, output_type = map_primitives.get_map_fn(sop_in.annotations["type"])
    sop_out = rasp.Map(fn, sop_in)
    return utils.annotate_type(sop_out, type=output_type)


def sample_sequence_map(rng, variable_scope: list[rasp.SOp]):
    """Sample a sequence map. A SM applies a function elementwise to
    two categorical SOps. The output is always categorical."""
    args = sample_from_scope(
        rng, 
        variable_scope, 
        type_constraint="categorical", 
        size=2, 
        replace=False
    )
    fn = rng.choice(map_primitives.NONLINEAR_SEQMAP_FNS)
    sop_out = rasp.SequenceMap(fn, *args)
    return utils.annotate_type(sop_out, type="categorical")


def sample_linear_sequence_map(rng, variable_scope: list):
    """Sample a linear sequence map. A LNS linearly combines two
    numerical SOps. The output is always numerical."""
    args = sample_from_scope(
        rng, 
        variable_scope, 
        type_constraint="float", 
        size=2, 
        replace=False
    )
    weights = np.clip(rng.normal(size=2) + 1, 0, 2)  # TODO: sometimes use 1,1 weights?
    sop_out = rasp.LinearSequenceMap(*args, *weights)
    return utils.annotate_type(sop_out, type="float")


def sample_selector(rng, variable_scope: list):
    """Sample a rasp.Select. A select takes two categorical SOps and
    returns a selector (matrix) of booleans."""
    # TODO: allow Selectors with bools (numerical & 0-1) as input?
    sop_in1, sop_in2 = sample_from_scope(
        rng,
        variable_scope,
        type_constraint="categorical",
        other_constraints=[lambda sop: None not in sop(TEST_INPUT)],
        size=2,
        replace=True,
    )
    comparison = rng.choice(map_primitives.COMPARISONS)
    selector = rasp.Select(sop_in1, sop_in2, comparison)
    return selector


def sample_numerical_aggregate(rng, variable_scope: list):
    """
    Tracr puts constraints on select-aggregate operations. This aggregate is 
    sampled to satisfy the constraint that the sop argument is 'boolean',
    that is numerical and only takes values 0 or 1.
    This constraint is necessary for all aggregates with numerical SOps.
    """
    selector = sample_selector(rng, variable_scope)
    sop_in = sample_from_scope(
        rng,
        variable_scope,
        type_constraint="bool",
        other_constraints=[lambda sop: None not in sop(TEST_INPUT)]
    )
    sop_out = rasp.Aggregate(selector, sop_in, default=0)
    # TODO: sometimes output can be bool here?
    return utils.annotate_type(sop_out, type="float")  # has to be numerical (tracr constraint)


def sample_categorical_aggregate(rng, variable_scope: list, max_retries=10):
    """
    Sample an aggregate operation with a categorical SOp. Categorical aggregate
    operations must satisfy the constraint that there is no aggregation (eg averaging).
    This usually means that the selector has width 1, but it could also mean that a width > 1
    selector is used but the output domain of the aggregate is still equal to the input domain.
    """
    selector = sample_selector(rng, variable_scope)
    sop_in = sample_from_scope(
        rng,
        variable_scope,
        type_constraint="categorical",
        other_constraints=[lambda sop: None not in sop(TEST_INPUT)]
    )
    sop_out = rasp.Aggregate(selector, sop_in, default=None)

    # validate:
    width = max(rasp.SelectorWidth(selector)(TEST_INPUT))
    if width > 1 and set(sop_in(TEST_INPUT)) != set(sop_out(TEST_INPUT)):
        if max_retries > 0:
            sop_out = sample_categorical_aggregate(rng, variable_scope, max_retries=max_retries-1)
        else:
            raise SamplingError("Maximum retries reached. Could not sample categorical aggregate with valid output domain."
                                "This because the sampler couldn't find a selector with width 1, and other sampled selectors "
                                "don't result in an output domain that is a subset of the input domain.")

    return utils.annotate_type(sop_out, type="categorical")


def sample_selector_width(rng, variable_scope: list):
    selector = sample_selector(rng, variable_scope)
    sop_out = rasp.SelectorWidth(selector)
    return utils.annotate_type(sop_out, type="categorical")


SAMPLE_FUNCTIONS = {
    "map": sample_map,
    "sequence_map": sample_sequence_map,
    "linear_sequence_map": sample_linear_sequence_map,
    "numerical_aggregate": sample_numerical_aggregate,
    "categorical_aggregate": sample_categorical_aggregate,
    "selector_width": sample_selector_width,
}


def sample_sop(rng, variable_scope: list):
    """Sample a SOp."""
    sop_type = rng.choice(list(SAMPLE_FUNCTIONS.keys()))
    sop = SAMPLE_FUNCTIONS[sop_type](rng, variable_scope)
    test_output = sop(TEST_INPUT)
    frac_none = utils.fraction_none(test_output)
    if frac_none > 0.5:
        raise SamplingError(f"Sampled SOp {sop} has too many None values ({frac_none}).")
    return sop


def validate_custom_types(expr: rasp.SOp, test_input):
    out = expr(test_input)
    if expr.annotations["type"] == "bool":
        # bools are numerical and only take values 0 or 1
        if not set(out).issubset({0, 1, None}):
            raise ValueError(f"Bool SOps may only take values 0 or 1. Instead, received {out}")
        elif not rasp.numerical(expr):
            raise ValueError(f"Bool SOps must be numerical. Instead, {expr} is categorical.")
    elif expr.annotations["type"] == "float":
        # floats are numerical and can take any value
        if not rasp.numerical(expr):
            raise ValueError(f"Float SOps must be numerical. Instead, {expr} is categorical.")
    elif expr.annotations["type"] == "categorical":
        if not rasp.categorical(expr):
            raise ValueError(f"{expr} is annotated as type=categorical, but is actually numerical.")


def validate_compilation(expr: rasp.SOp, test_inputs: list):
    model = compiling.compile_rasp_to_model(expr, vocab={1,2,3,4}, max_seq_len=5, compiler_bos="BOS")
    for test_input in test_inputs:
        rasp_out = expr(test_input)
        rasp_out_sanitized = [0 if x is None else x for x in rasp_out]
        out = model.apply(["BOS"] + test_input).decoded[1:]

        if not np.allclose(out, rasp_out_sanitized, rtol=1e-3, atol=1e-3):
            raise ValueError(f"Compiled program {expr.label} does not match RASP output.\n"
                             f"Compiled output: {out}\n"
                             f"RASP output: {rasp_out}\n"
                             f"Test input: {test_input}\n"
                             f"SOp: {expr}")


class ProgramSampler:
    def __init__(self, validate_compilation=False, rng=None):
        self.sops = [rasp.tokens, rasp.indices]
        self.sops = [utils.annotate_type(sop, type="categorical") for sop in self.sops]
        self.validate_compilation = validate_compilation
        self.rng = np.random.default_rng(rng)

    def sample(self, n_sops=10):
        """Sample a program."""
        errs = []
        for _ in range(n_sops):
            try:
                sop = sample_sop(self.rng, self.sops)
                self.sops.append(sop)
            except (utils.EmptyScopeError, SamplingError) as err:
                errs.append(err)

        self.program = self.sops[-1]
        self.validate()
        return errs

    def validate(self):
        """Validate the program. This is fairly slow, especially when 
        self.validate_compilation is enabled."""
        sop = self.program
        validate_custom_types(sop, TEST_INPUT)
        errs = validate(sop, TEST_INPUT)
        if len(errs) > 0:
            raise ValueError(f"Invalid program: {errs}")
        elif self.validate_compilation:
            validate_compilation(sop, [TEST_INPUT])
        return