import os
import random
import re
import sys

import numpy as np

input_text = ['[CLS]', 'll', '##ei', '##da', '[', ']', '(', 'ste', '##ede', '##n', '##wi', '##is', 'uk', '[', ']', ';', 'spoon', '##sk', 'no', '##om', 'le', '##rid', '##a', '[', ']', 'as', 'en', 'st', '##aa', '##d', 'u', '##un', "'", 't', 'wa', '##ast', '##en', 'faa', '##n', 'kata', '##lo', '##oni', '##en', 'an', 'hood', '##sta', '##ad', 'faa', '##n', "'", 't', 'pro', '##win', '##s', 'll', '##ei', '##da', '.', 'hat', 'ha', '##a', 'ii', '##n', '##wen', '##ern', '(', 'stan', '##t', ')', '.', '[SEP]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]', '[PAD]']
mask_token_index = 10
special_token_index = 11




class SpanBERTMasking(object):
    """Given a stream of input text, creates pretraining examples."""

    def __init__(self, hf_dset, hf_tokenizer, max_length, text_col='text', lines_delimiter='\n',
                 minimize_data_size=True, apply_cleaning=True, geometric_p=0.3, mlm_probability=0.15,
                 replace_prob=0.1,
                 orginal_prob=0.1,
                 ignore_index=-100):
        self.hf_tokenizer = hf_tokenizer
        self._current_sentences = []
        self._current_length = 0
        self._max_length = max_length
        self._target_length = max_length
        self.hf_dset = hf_dset
        self.text_col = text_col
        self.lines_delimiter = lines_delimiter
        self.minimize_data_size = minimize_data_size
        self.apply_cleaning = apply_cleaning
        self.lower = 1
        self.upper = 10
        self.lens = list(range(self.lower, self.upper + 1))
        self.p = geometric_p
        self.len_distrib = [self.p * (1 - self.p) ** (i - self.lower) for i in
                            range(self.lower, self.upper + 1)] if self.p >= 0 else None
        self.len_distrib = [x / (sum(self.len_distrib)) for x in self.len_distrib]

    def mask(self, sentence):
        sentence_length = len(sentence)
        mask_num = None
        pass


class SpanBERTDataProcessor(object):
    """Given a stream of input text, creates pretraining examples."""

    def __init__(self, hf_dset, hf_tokenizer, max_length, text_col='text', lines_delimiter='\n',
                 minimize_data_size=True, apply_cleaning=True):
        self.hf_tokenizer = hf_tokenizer
        self._current_sentences = []
        self._current_length = 0
        self._max_length = max_length
        self._target_length = max_length
        self.hf_dset = hf_dset
        self.text_col = text_col
        self.lines_delimiter = lines_delimiter
        self.minimize_data_size = minimize_data_size
        self.apply_cleaning = apply_cleaning

    def map(self, **kwargs):
        "Some settings of datasets.Dataset.map for ELECTRA data processing"
        num_proc = kwargs.pop('num_proc', os.cpu_count())
        return self.hf_dset.my_map(
            function=self,
            batched=True,
            remove_columns=self.hf_dset.column_names,  # this is must b/c we will return different number of rows
            disable_nullable=True,
            input_columns=[self.text_col],
            writer_batch_size=10 ** 4,
            num_proc=num_proc,
            **kwargs
        )

    def __call__(self, texts):
        if self.minimize_data_size:
            new_example = {'input_ids': [], 'sentA_length': []}
        else:
            new_example = {'input_ids': [], 'input_mask': [], 'segment_ids': []}

        for text in texts:  # for every doc

            for line in re.split(self.lines_delimiter, text):  # for every paragraph

                if re.fullmatch(r'\s*', line): continue  # empty string or string with all space characters
                if self.apply_cleaning and self.filter_out(line): continue

                example = self.add_line(line)
                if example:
                    for k, v in example.items(): new_example[k].append(v)

            if self._current_length != 0:
                example = self._create_example()
                for k, v in example.items(): new_example[k].append(v)

        return new_example

    def filter_out(self, line):
        if len(line) < 80: return True
        return False

    def clean(self, line):
        # () is remainder after link in it filtered out
        return line.strip().replace("\n", " ").replace("()", "")

    def add_line(self, line):
        """Adds a line of text to the current example being built."""
        line = self.clean(line)
        print("For line: ", line)
        # tokens = self.hf_tokenizer.tokenize(line)
        # tokids = self.hf_tokenizer.convert_tokens_to_ids(tokens)
        self._current_sentences.append(line)
        self._current_length += len(line)
        if self._current_length >= self._target_length:
            return self._create_example()
        return None

    def _create_example(self):
        """Creates a pre-training example from the current list of sentences."""
        # small chance to only have one segment as in classification tasks
        if random.random() < 0.1:
            first_segment_target_length = 100000
        else:
            # -3 due to not yet having [CLS]/[SEP] tokens in the input text
            first_segment_target_length = (self._target_length - 3) // 2

        first_segment = ""
        second_segment = ""

        # print("current: ", self._current_sentences)

        for sentence in self._current_sentences:
            # the sentence goes to the first segment if
            # (1) the first segment is empty
            # (2) the sentence doesn't put the first segment over length or
            # (3) 50% of the time when it does put the first segment over length
            if (len(first_segment) == 0 or
                    len(first_segment) + len(sentence) < first_segment_target_length):
                first_segment += sentence
            else:
                second_segment += sentence
        # trim to max_length while accounting for not-yet-added [CLS]/[SEP] tokens
        first_segment = first_segment[:self._max_length - 2]
        second_segment = second_segment[:max(0, self._max_length -
                                             len(first_segment) - 3)]

        # prepare to start building the next example
        self._current_sentences = []
        self._current_length = 0
        # small chance for random-length instead of max_length-length example
        if random.random() < 0.05:
            self._target_length = random.randint(5, self._max_length)
        else:
            self._target_length = self._max_length
        result = self._make_example(first_segment, second_segment)
        print(result)
        return result

    def _make_example(self, first_segment, second_segment):
        """Converts two "segments" of text into a tf.train.Example."""
        print(f' first: {first_segment}, second : {second_segment}')
        input_ids = self.hf_tokenizer.cls_token + " "+ first_segment + " " + self.hf_tokenizer.sep_token
        sentA_length = len(input_ids)
        segment_ids = [0] * sentA_length
        if second_segment:
            input_ids += second_segment + self.hf_tokenizer.sep_token
            segment_ids += [1] * (len(second_segment) + 1)

        if self.minimize_data_size:
            return {
                'input_ids': input_ids,
                'sentA_length': sentA_length,
            }
        else:
            input_mask = [1] * len(input_ids)
            input_ids += [0] * (self._max_length - len(input_ids))
            input_mask += [0] * (self._max_length - len(input_mask))
            segment_ids += [0] * (self._max_length - len(segment_ids))
            return {
                'input_ids': input_ids,
                'input_mask': input_mask,
                'segment_ids': segment_ids,
            }
