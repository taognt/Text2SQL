import sqlparse
import sqlvalidator
import re
from sqlparse.sql import Identifier, IdentifierList
from sqlparse.tokens import Keyword, DML, Whitespace
from parameters import classification_prompt, prompt_schema, score_prompt
from itertools import permutations
import sqlite3
from sqlite3 import Cursor
import random
import string
import pandas as pd

convert_type = {
    "text": "TEXT",
    "number": "INTEGER",
    "time": "TEXT",
    "boolean": "TEXT",
    "others": "TEXT",
}

def generate_synth_data(type_: str, pimary: str):

    nb_elem = 50
    word_lenght = 6
    max_integer = 60

    if type_=="TEXT" and pimary=="PRIMARY KEY":
        unique_strings = set()
        while len(unique_strings) < nb_elem:
            unique_strings.add(''.join(random.choices(string.ascii_uppercase + string.digits, k=word_lenght)))
        return list(unique_strings)
    
    elif type_=="TEXT" and not pimary=="PRIMARY KEY":
        return [
            ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(word_lenght))
            for _ in range(nb_elem)
        ]
    
    elif type_=="INTEGER" and not pimary=="PRIMARY KEY":
        return random.choices(list(range(max_integer)), k=nb_elem)
    
    elif type_=="INTEGER" and  pimary=="PRIMARY KEY":    
        return random.sample(list(range(max_integer)), k=nb_elem)
    
    else:
        print("ERROR TYPE")

def generate_synthetic_db(db_schema: pd.DataFrame) -> dict[str, Cursor]:
    sql_databases: dict[str, Cursor] = {}

    for i, db in db_schema.iterrows():

        conn = sqlite3.connect(":memory:")
        sql_databases[db["db_id"]] = conn.cursor()

        schema = re.split(r'\|', db["Schema (values (type))"])

        p_keys_dict = {}
        for p_key in re.split(r'\|', db["Primary Keys"]):
            if len(p_key) > 0:
                p_key_split = re.split(r':', p_key)
                p_keys_dict[p_key_split[0].strip()] = p_key_split[1].strip()

        for table in schema:
            table_split = re.split(r':', table)
            table_name = table_split[0].strip()

            att_names = []
            att_types = []
            att_synth_data = []

            rows_att = []

            for attribute_type in re.split(r',', table_split[1]):
                if match_ := re.match(r'(.*)\s\((.*)\)', attribute_type):
                    att_name = match_.group(1).strip().replace(" ", "_")
                    att_type = match_.group(2).strip()
                    
                    # Primary Key
                    if table_name in p_keys_dict.keys() and p_keys_dict[table_name] == att_name:
                        primary = "PRIMARY KEY"
                    else:
                        primary = None

                    att_names.append(att_name)
                    att_types.append(att_type)
                    att_synth_data.append(generate_synth_data(convert_type[att_type], primary))

                    rows_att.append(f'"{att_name}" {convert_type[att_type]}{" "+primary if primary is not None else ""}')

            create_request = f"CREATE TABLE \"{table_name}\" (\n    {',\n    '.join(rows_att)}\n)"
            insert_request = f"INSERT INTO \"{table_name}\" (\"{'\", \"'.join(att_names)}\") VALUES ({', '.join(['?']*len(att_names))})"

            try:
                sql_databases[db["db_id"]].execute(create_request)
                sql_databases[db["db_id"]].executemany(insert_request, list(zip(*att_synth_data)))
            except Exception as e:
                print(f">>> ERROR - i={i} / db : {db["db_id"]} / table : {table_name}")
                print(e, "\n")
                print(create_request)
                print(insert_request, "\n")
    
    return sql_databases

def compute_metrics(pred: str, ground_truth: str, db_id: str, sql_databases: dict[str, Cursor]):

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

    #### result_metric
    cursor = sql_databases[db_id]

    try:
        cursor.execute(pred)
        results1 = cursor.fetchall()
    
        cursor.execute(ground_truth)
        results2 = cursor.fetchall()

        result_metric = int(results1==results2)
    except Exception as e:
        print(f"ERROR (db :{db_id}) : {e}")
        result_metric = 0

    return {
        "valid_pred": valid_pred,
        "keyword_score": keyword_score,
        "identifiers_score": identifiers_score,
        "result_metric": result_metric
    }