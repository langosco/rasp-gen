import os
import pytest
import numpy as np
import shutil
import jax


from decompile_tracr.sampling import rasp_utils
from decompile_tracr.sampling import sampling
from decompile_tracr.tokenizing import tokenizer
from decompile_tracr.tokenizing import vocab
from decompile_tracr.dataset import config
from decompile_tracr.dataset import generate
from decompile_tracr.dataset import tokenize_lib
from decompile_tracr.dataset import dedupe
from decompile_tracr.dataset import compile
from decompile_tracr.dataset import data_utils


rng = np.random.default_rng()


def test_sampling(base_dir, make_test_data):
    #data = data_utils.load_batches(base_dir / "unprocessed")
    pass


def test_deduplication(make_test_data):
    pass


def test_tokenization(base_dir, make_test_data):
    """De-tokenize, then re-tokenize. Ensure that the re-tokenized
    program is the same as the original."""
    data = data_utils.load_batches_from_subdirs(base_dir / "deduped")
    for x in data:
        program = tokenizer.detokenize(x['tokens'])
        retokenized = tokenizer.tokenize(program)
        assert x['tokens'] == retokenized, (
            f"tokenize(detokenize(x)) does not equal x."
        )


def test_compilation(base_dir, make_test_data):
    # this is hard because we can't easily load a compiled model
    # once we saved the weights.
    pass