# model selection
We need a model to add categories to spend data. Categories are the 8 Consumer Price Index categories. 
The spend data is structured and generally contains: date, description, quantity, price. 

Models to try:
| Model                                                                                      | Downloads (last month) | Parameters |
|:--------------------------------------------------------------------------------------------|:-----------------------|:-----------|
| [bart-large-mnli](https://huggingface.co/facebook/bart-large-mnli)                          | 3 mil                  | 0.4B       |
| [nli-distilroberta-base](https://huggingface.co/cross-encoder/nli-distilroberta-base)       | -                      | 0.04B      |
| [zero-shot-classify-SSTuning-XLM-R](https://huggingface.co/DAMO-NLP-SG/zero-shot-classify-SSTuning-XLM-R) | -                      | 0.03B      |

## Classification Approaches
Below are some model families.
| Approach                                                                   | Pros                                            | Cons                           |
|:---------------------------------------------------------------------------|:------------------------------------------------|:-------------------------------|
| **Tune a Pre-trained transformer model** (ex. DistilBERT)                  | High accuracy, leverages pre-training           | Requires labeled training data |
| **Use a Zero-shot classification**                                         | No tuning or training needed, works out-of-box  | Slower inference               |
| **Classical machine learning pipeline** (ex. TF-IDF + Logistic Regression) | Fast, surprisingly effective, interpretable     | Lower accuracy on edge cases   |
**Recommendation for MVP:** Start with zero-shot or TF-IDF; upgrade to fine-tuned DistilBERT if accuracy becomes a bottleneck.

## Inference costs
Parameters are all the numerical values inside a model that it “learned” during training. Think of them as the model’s “brain weights” — they control how the model makes decisions.
Simple analogy: If a model is like a very complex decision tree, each parameter is like a small rule or weight that says “this word matters this much” or “this pattern is important.”

Why you care:
| Impact          | Details                                                                                                          |
|:----------------|:-----------------------------------------------------------------------------------------------------------------|
| **Performance** | 125M can capture nuanced patterns, 768M for complex relationships (but with diminishing returns at 100B+).       |
| **Speed**       | Slower; takes longer to run (inference time).                                                                    |
| **Size**        | Larger file size; needs more storage/memory to load.                                                             |
| **Compute**     | More compute required; harder for laptops, needs better GPUs.                                                   |
| **Cost**        | Higher cost; especially for cloud APIs.                                                                          |
For spending categorization :
| Model         | Params | Speed     | Quality | Use When                            |
|:--------------|:-------|:----------|:--------|:------------------------------------|
| DistilBERT    | 66M    | Very Fast | Good    | MVP, limited compute                |
| RoBERTa-base  | 125M   | Fast      | Better  | Balanced option                     |
| RoBERTa-large | 355M   | Slower    | Best    | You have compute & accuracy matters |

My recommendation: Start with 125M or smaller. Categorizing “paper towels” vs “shirt” doesn’t require 768M parameters. You get 90% of the performance at 50% of the cost.
