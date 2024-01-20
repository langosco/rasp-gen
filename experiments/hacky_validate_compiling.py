from collections import defaultdict
from tracr.rasp import rasp
from tracr.compiler import compiling
from rasp_generator import sampling
import numpy as np


rng = np.random.default_rng()

def compile_rasp_to_model(sop: rasp.SOp, vocab={0,1,2,3,4}, max_seq_len=5, compiler_bos="BOS"):
    return compiling.compile_rasp_to_model(
        sop,
        vocab=vocab,
        max_seq_len=max_seq_len,
        compiler_bos=compiler_bos
    )


def sample_test_input(rng, vocab={0,1,2,3,4}, max_seq_len=5):
    seq_len = rng.choice(range(1, max_seq_len+1))
    return rng.choice(list(vocab), size=seq_len)


test_inputs = [sample_test_input(rng) for _ in range(100)]
test_inputs += [[0], [0,0,0,0,0], [4,4,4,4], [0,1,2,3]]


n_samples = 100
errs = defaultdict(list)
results = []


print(f"Sampling {n_samples} programs...")
for _ in range(n_samples):
    try:
        sampler = sampling.ProgramSampler(rng=rng)
        retries = sampler.sample(n_sops=30)
        errs['retries'] += retries
        results.append(dict(program=sampler.program))
    except Exception as err:
        errs['sampling'].append(err)
    

print(f"Done sampling. Total programs sampled (minus sampling failures): {len(results)}")
print("Total sampling retries:", len(errs['retries']))
print("Total sampling failures:", len(errs['sampling']))
print("Now compiling and validating...")


for r in results:
    if 'model' not in r:
        continue
    try:
        model = compile_rasp_to_model(r['program'])
        r['model'] = model
    except Exception as err:
        errs['compilation'].append(err)
        r['compilation_error'] = err


print("Done compiling.")
print("Total programs compiled:", len(results) - len(errs['compilation']))
print("Total compilation errors:", len(errs['compilation']))
print("Now validating...")


for r in results:
    if 'model' not in r:
        continue
    for x in test_inputs:
        rasp_out = r['program'](x)
        rasp_out_sanitized = [0 if x is None else x for x in rasp_out]
        model_out = r['model'].apply(["BOS"] + x).decoded[1:]
        if not np.allclose(model_out, rasp_out_sanitized, rtol=1e-3, atol=1e-3):
            err = ValueError(f"Compiled program {r['program'].label} does not match RASP output.\n"
                                f"Compiled output: {model_out}\n"
                                f"RASP output: {rasp_out}\n"
                                f"Test input: {x}\n")
            errs['validation'].append(err)
            r['validation_error'] = err
            break


print("Total programs compiled validly (relative to test inputs):", len(results) - len(errs['validation']))
print("Validation errors:", len(errs['validation']))