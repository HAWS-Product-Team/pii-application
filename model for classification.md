# model selection
We need a model to add categories to spend data. Categories are the 8 Consumer Price Index categories. 
The spend data is structured and generally contains: date, description, quantity, price. 

here are some models to try:
- https://huggingface.co/facebook/bart-large-mnli
-- 3 mil downloads last month
-- .4B parameters 
- https://huggingface.co/cross-encoder/nli-distilroberta-base
-- .04B parameters 
- https://huggingface.co/DAMO-NLP-SG/zero-shot-classify-SSTuning-XLM-R
-- .03B

# background

Parameters are all the numerical values inside a model that it “learned” during training. Think of them as the model’s “brain weights” — they control how the model makes decisions.
Simple analogy: If a model is like a very complex decision tree, each parameter is like a small rule or weight that says “this word matters this much” or “this pattern is important.”
Why you care:
More parameters = potentially better performance:
	∙	125M parameters can capture more nuanced patterns
	∙	768M parameters can understand more complex relationships
	∙	But… diminishing returns (100B parameters might only be slightly better)
But more parameters also means:
	∙	Slower — takes longer to run (inference time)
	∙	Larger file size — needs more storage/memory to load
	∙	More compute required — harder to run on laptops, needs better GPUs
	∙	Higher cost — if using cloud APIs, you pay more
For spending categorization :
|Model        |Params|Speed    |Quality|Use When                           |
|-------------|------|---------|-------|-----------------------------------|
|DistilBERT   |66M   |Very Fast|Good   |MVP, limited compute               |
|RoBERTa-base |125M  |Fast     |Better |Balanced option                    |
|RoBERTa-large|355M  |Slower   |Best   |You have compute & accuracy matters|

My recommendation: Start with 125M or smaller. Categorizing “paper towels” vs “shirt” doesn’t require 768M parameters. You get 90% of the performance at 50% of the cost.

