"""
Dispatcher logic:
The dispatcher selects a strategy based on source_type, not text length. 
Source_type tells us not just how long a document typically is, but how it's structured 
and what split quality is needed. Character or token count is not a factor.

"""