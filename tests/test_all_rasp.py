# %%

# Assume that script/generate_data.py and script/dedupe.py has already been run
# and that the data has been saved to ../data/deduped/test_progs/data.pkl

# import numpy as np
# from rasp_generator import sampling, utils


import pickle
from tqdm import tqdm
import numpy as np
import numpy as np
import random
import rasp_generator

# import os

# # Set JAX to use CPU
# os.environ["JAX_PLATFORM_NAME"] = "cpu"

__MAIN__ = "__main__"

# %%
from rasp_tokenizer import data_utils
    
    
def generate_random_input(model):
    size_input = model.input_encoder._max_seq_len - 1  # account for BOS token
    bound_input = model.input_encoder.vocab_size - 2  # account for compiler pad token and BOS token

    return np.random.randint(0, bound_input, size_input).tolist()

    
def get_model_output(input, rasp, model=None):
    raw_output_rasp = rasp(input)
    output_rasp = np.array(raw_output_rasp)
    
    output_model = None
    if model is not None:
        raw_output_model = model.apply(["compiler_bos"] + input).decoded[1:]
        output_model = np.array(raw_output_model)

    return output_rasp, output_model


def test_functionality_rasp_and_compiled(data,
                                        num_inputs=100, 
                                         seed=None,
                                         atol = 0.1,
                                         rtol = 0.1,
                                         verbose = False):
    random.seed(seed)
    np.random.seed(seed)
        
    # if data is None:
    #     with open(data_path, "rb") as file:
    #         data = pickle.load(file)
        
    for i, datapoint in tqdm(enumerate(data), total=len(data)):
        
        for _ in range(num_inputs):
            
            model = datapoint['model']
            rasp = datapoint['rasp']
            
            input = generate_random_input(model)
            output_rasp, output_model = get_model_output(input, rasp, model)
            
            error = False
      
            # check if any of the inputs are None
            if any([x is None for x in output_rasp]):
                raise ValueError(f"Output RASP {output_rasp}\n",
                                 f"Output model {output_model}\n",
                                 f"RASP contains None: for model '{i}' and input '{input}':\n")
            
            # if model is not floating, convert
            if not np.issubdtype(output_model.dtype, np.floating):
                output_model = output_model.astype(np.float32)
                
            if not np.issubdtype(output_rasp.dtype, np.floating):
                output_rasp = output_rasp.astype(np.float32)
    
            if not np.allclose(output_rasp, output_model, atol=atol, rtol=rtol):
                if verbose:
                    rasp_generator.utils.print_program(rasp)
                raise ValueError(f"Outputs are not close for model '{i}' and input '{input}':\n",
                                    f"Output RASP: {output_rasp}\n",
                                    f"Output Model: {output_model}\n")

# %%
def test_non_constant_program(data,
                            num_inputs=10, 
                                seed=None,
                                epsilon = 0.01,
                                verbose = False):
    random.seed(seed)
    np.random.seed(seed)
        
    # if data is None:
    #     with open(data_path, "rb") as file:
    #         data = pickle.load(file)
    count_constant = 0
        
    for i, datapoint in tqdm(enumerate(data), total=len(data)):
        
        outputs = []
        for _ in range(num_inputs):
            
            model = datapoint['model']
            rasp = datapoint['rasp']
            
            input = generate_random_input(model)
            output_rasp, _ = get_model_output(input, rasp)
          
            outputs.append(output_rasp)
        outputs = np.stack(outputs, axis = 0)
        variance = np.var(outputs, axis = 0)
        #print(f"Variance for model '{i}':\n", variance.max())
        if variance.mean() < epsilon:
            print(f"Model {i} is constant:")
            if verbose:
                print("=====================================")
                rasp_generator.utils.print_program(rasp)
                print("")
            count_constant += 1
            
    print(f"Number of constant models: {count_constant}/{len(data)}")
            #raise ValueError(f"Model is constant '{i}':\n")


# %%

if __name__ == __MAIN__:
    
    data = data_utils.load_batches(keep_aux=True)  # loads data generated by generate_data.py, including model & rasp
    deduped = data_utils.load_deduped(name = "pytest", flatten=False, keep_aux=True)  # loads data post-deduplication
    test_non_constant_program(deduped, num_inputs = 100, seed=42, verbose = True)
    #test_functionality_rasp_and_compiled(deduped, seed=42, verbose = True)

# %%
import matplotlib.pyplot as plt
mlp0_in = data[0]['model'].params['transformer/layer_0/mlp/linear_1']['w']
plt.imshow(mlp0_in)
plt.colorbar()
# %%
