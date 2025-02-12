import sqlparse
import sqlvalidator
import re
from sqlparse.sql import Identifier, IdentifierList
from sqlparse.tokens import Keyword, DML, Whitespace
from parameters import classification_prompt, prompt_schema, score_prompt
from itertools import permutations


def get_words_between_keywords(sql: str) -> list[tuple[str, list[str]]]:

    """
    Parse a SQL request to transform it into this format :

    [('SELECT', ['Status']),
    ('FROM', ['city']),
    ('GROUP BY', ['Status']),
    ('ORDER BY', ['COUNT(*)', 'DESC']),
    ('LIMIT', ['1'])]
    """

    parsed = sqlparse.parse(sql)[0]  # Parse the SQL statement
    tokens = parsed.tokens
    
    words_between = []  # To store words between keywords
    current_keywords = []
    buffer = []

    for token in tokens:
        if token.ttype in (Keyword, DML):  # Check if the token is a keyword
            if buffer:  # If there are words in the buffer, add them
                words_between.append((current_keywords[-1] if current_keywords else None, buffer))
                buffer = []
            current_keywords.append(token.value.upper())
        elif token.ttype is Whitespace:  # Ignore whitespace
            continue
        else:
            if isinstance(token, (Identifier, IdentifierList)):
                buffer.append(token.get_real_name() or token.value)
            else:
                buffer.append(token.value)
    
    if buffer:  # Add remaining buffer
        words_between.append((current_keywords[-1] if current_keywords else None, buffer))
    
    return words_between


# def compute_metrics(pred: str, ground_truth: str):

#     """Compare 2 queries on their semantic
    
#     Return :
    
#     - valid_pred : True if te pred query is semanticaly correct, False otherwise. It is not really reliable.
#     - keyword_score [0, 1]: Equivalent of F1 score for SQL keywords presence. The pred query must contains the keywords of the ground truth without adding new keywords.
#     - identifier_score [0, 1]: For each keywords, f1 score is computed for identifiers words (table name, attributes...). The average gives the identifier_score.
    
#     """


#     # Check if the predicted query is semanticaly correct
#     parsed_pred = sqlvalidator.parse(pred)
#     valid_pred = False
#     try:
#         if parsed_pred.is_valid():
#             valid_pred = True
#     except:
#         valid_pred = False

#     # Normalize queries
#     normalized_pred = sqlparse.format(pred, reindent=False, keyword_case='upper')
#     normalized_gt = sqlparse.format(ground_truth, reindent=False, keyword_case='upper')

#     # Compare Semantic of queries
#     tokens_pred = get_words_between_keywords(normalized_pred)
#     tokens_gt = get_words_between_keywords(normalized_gt)

#     """example of tokens_pred or tokens_gt : 
    
#     [('SELECT', ['Status']),
#     ('FROM', ['city']),
#     ('GROUP BY', ['Status']),
#     ('ORDER BY', ['COUNT(*)', 'DESC']),
#     ('LIMIT', ['1'])]
#     """

#     def compute_f1score(a: set, b: set):
#         """Equivalent of F1 score metric"""
#         TP = len(a & b)
#         FP = len(a - b)
#         FN = len(b - a)

#         return TP / (TP + 0.5*(FP + FN))

#     ## Keyword score

#     keywords_pred = set([elem[0] for elem in tokens_pred])
#     keywords_gt = set([elem[0] for elem in tokens_gt])

#     keyword_score = compute_f1score(keywords_pred, keywords_gt)
    
#     ## Identifier score

#     identifier_score = 0
#     commun_keywords = keywords_pred & keywords_gt
#     for kw in list(commun_keywords):
#         identifiers_pred = next((item for item in tokens_pred if item[0] == kw), None)[1]
#         identifiers_gt = next((item for item in tokens_gt if item[0] == kw), None)[1]

#         identifier_score += compute_f1score(set(identifiers_pred), set(identifiers_gt))
    
#     identifier_score = identifier_score / len(commun_keywords)

#     return valid_pred, keyword_score, identifier_score, tokens_pred, tokens_gt


def compute_metrics(pred: str, ground_truth: str):

    """Compare 2 queries on their semantic
    
    Return :
    
    - valid_pred : True if te pred query is semanticaly correct, False otherwise. It is not really reliable.
    - keyword_score [0, 1]: Equivalent of F1 score for SQL keywords presence. The pred query must contains the keywords of the ground truth without adding new keywords.
    - identifier_score [0, 1]: For each keywords, f1 score is computed for identifiers words (table name, attributes...). The average gives the identifier_score.
    
    """

    def compute_f1score(a: set, b: set, eps: float=1e-4):
        """Equivalent of F1 score metric"""
        TP = len(a & b)
        FP = len(a - b)
        FN = len(b - a)

        return (TP + eps) / (TP + 0.5*(FP + FN) + eps)
    
    valid_pred = True

    SQL_keywords = ["SELECT", "WHERE", "FROM", "HAVING", "GROUP BY", "LIMIT", "DESC", "ASC"]

    keywords_pred = [word for word in SQL_keywords if word.upper() in pred.upper()]
    keywords_gt = [word for word in SQL_keywords if word.upper() in ground_truth.upper()]

    keyword_score = compute_f1score(set(keywords_pred), set(keywords_gt))

    ### IDENTIFIERS

    dict_identifiers_pred = {kw: set() for kw in SQL_keywords}
    dict_identifiers_gt = {kw: set() for kw in SQL_keywords}

    pattern = r'(' + '|'.join(map(re.escape, SQL_keywords)) + r')'
    
    # Split text while keeping the keywords in the result
    pred_parts = re.split(pattern, pred.upper())
    gt_parts = re.split(pattern, ground_truth.upper())

    for i, part in enumerate(pred_parts):
        if part in SQL_keywords:
            kw = part
            identifiers = re.split(r'\s+', pred_parts[i+1])
            identifiers = [elem.replace(",", "") for elem in identifiers if elem != ""]
            dict_identifiers_pred[kw] = set(identifiers)

    for i, part in enumerate(gt_parts):
        if part in SQL_keywords:
            kw = part
            identifiers = re.split(r'\s+', gt_parts[i+1])
            identifiers = [elem.replace(",", "") for elem in identifiers if elem.replace(",", "") != ""]
            dict_identifiers_gt[kw] = set(identifiers)

    identifiers_scores = []
    for kw in SQL_keywords:
        if len(dict_identifiers_gt[kw]) + len(dict_identifiers_pred[kw]) > 1:
            identifiers_scores.append(
                compute_f1score(dict_identifiers_pred[kw], dict_identifiers_gt[kw])
            )

    identifiers_score = sum(identifiers_scores)/len(identifiers_scores)


    return valid_pred, keyword_score, identifiers_score