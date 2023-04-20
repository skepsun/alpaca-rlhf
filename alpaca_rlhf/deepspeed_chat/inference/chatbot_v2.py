# Copyright (c) Microsoft Corporation.
# SPDX-License-Identifier: Apache-2.0

# DeepSpeed Team

import argparse
import re
import logging
import transformers  # noqa: F401
from transformers import pipeline, set_seed
from transformers import AutoConfig, OPTForCausalLM, AutoTokenizer
from transformers import GenerationConfig
import torch


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path",
                        type=str,
                        default='facebook/opt-125m',
                        help="Directory containing trained actor model")
    parser.add_argument(
        "--max_new_tokens",
        type=int,
        default=128,
        help="Maximum new tokens to generate per response",
    )
    args = parser.parse_args()
    return args


class Generator:
    """

    :return:
    """

    def __init__(self, model, tokenizer):
        """

        :param model:
        :param tokenizer:
        """
        self.model = model
        self.tokenizer = tokenizer

    def generate(self, prompt, max_new_tokens=256):
        """

        :param prompt:
        :return:
        """
        if torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"
        input_ids = self.tokenizer.encode(prompt, return_tensors='pt').to(device)

        # generate text until the output length (which includes the context length) reaches 50
        generation_config = GenerationConfig(
            max_new_tokens=max_new_tokens,
            do_sample=True,
            top_k=50,
            temperature=0.7,
            top_p=0.92,
        )
        sample_output = self.model.generate(input_ids, max_length=max_new_tokens,
                                            min_length=max_new_tokens)

        response = self.tokenizer.decode(sample_output[0], skip_special_tokens=True)
        result = [{'generated_text': response}]
        return result


def get_generator(path):
    tokenizer = AutoTokenizer.from_pretrained(path, fast_tokenizer=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    model_config = AutoConfig.from_pretrained(path)
    model = OPTForCausalLM.from_pretrained(path,
                                           from_tf=bool(".ckpt" in path),
                                           config=model_config, device_map='auto')
    model.eval()
    model.config.end_token_id = tokenizer.eos_token_id
    model.config.pad_token_id = model.config.eos_token_id
    model.resize_token_embeddings(len(tokenizer))

    generator = Generator(model, tokenizer)

    return generator


def get_user_input(user_input):
    # tmp = input("Enter input (type 'quit' to exit, 'clear' to clean memory): ")
    tmp = 'Who are you?'
    new_inputs = f"Human: {tmp}\n Assistant: "
    user_input += f" {new_inputs}"
    return user_input, tmp == "quit", tmp == "clear"


def get_model_response(generator: Generator, user_input, max_new_tokens):
    response = generator.generate(user_input, max_new_tokens=max_new_tokens)
    return response


def process_response(response, num_rounds):
    output = str(response[0]["generated_text"])
    output = output.replace("<|endoftext|></s>", "")
    all_positions = [m.start() for m in re.finditer("Human: ", output)]
    place_of_second_q = -1
    if len(all_positions) > num_rounds:
        place_of_second_q = all_positions[num_rounds]
    if place_of_second_q != -1:
        output = output[0:place_of_second_q]
    return output


def main(args):
    generator = get_generator(args.path)
    set_seed(42)

    user_input = ""
    num_rounds = 0
    while True:
        num_rounds += 1
        user_input, quit, clear = get_user_input(user_input)

        if quit:
            break
        if clear:
            user_input, num_rounds = "", 0
            continue

        response = get_model_response(generator, user_input,
                                      args.max_new_tokens)
        output = process_response(response, num_rounds)

        print("-" * 30 + f" Round {num_rounds} " + "-" * 30)
        print(f"{output}")
        user_input = f"{output}\n\n"


if __name__ == "__main__":
    # Silence warnings about `max_new_tokens` and `max_length` being set
    logging.getLogger("transformers").setLevel(logging.ERROR)

    args = parse_args()
    main(args)

# Example:
"""
 Human: what is internet explorer?
 Assistant:
Internet Explorer is an internet browser developed by Microsoft. It is primarily used for browsing the web, but can also be used to run some applications. Internet Explorer is often considered the best and most popular internet browser currently available, though there are many other options available.

 Human: what is edge?
 Assistant:
 Edge is a newer version of the Microsoft internet browser, developed by Microsoft. It is focused on improving performance and security, and offers a more modern user interface. Edge is currently the most popular internet browser on the market, and is also used heavily by Microsoft employees.
"""