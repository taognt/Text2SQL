prompt_schema = "Based on the SQL schema, write a SQL query that answer the user's question. Answer only the SQL query. First take a look at the schema: {schema}.\nQuestion: {question}.\nSQL Query:"

classification_prompt = """Determine if the two SQL queries are logically equivalent assuming the same schema, data, and execution environment. Follow these guidelines:

- Focus on the logical structure and intent of the queries, not superficial differences such as formatting or column aliases.
- Be indulgent with column names that differ slightly (e.g., column1 vs. col1) but ensure that logic and relationships between tables remain consistent.
- If the queries are not equivalent, provide a brief correction or explanation of how one query could be adjusted to match the other.
- Provide your answer as 'Yes' or 'No' only, followed by the correction if applicable.

Query:
{query}

Generated query:
{generated_query}

Same (Yes or No, Correction if necessary):"""

score_prompt = """Determine the degree of logical equivalence between the two SQL queries, assuming the same schema, data, and execution environment. Provide a score between 0 and 1, where:

- 1: Fully logically equivalent (queries produce identical results under all circumstances).
- 0: Completely different (queries are logically unrelated or produce entirely different results).
- Scores between 0 and 1 should reflect partial equivalence, considering factors such as:
  - Differences in filters, conditions, or joins that partially overlap.
  - Minor variations in selected columns or formatting that do not affect the overall logic.
  - Similar intent but differing specifics in query structure.

Explain your score briefly, highlighting key differences or similarities that influenced the rating.

Query 1:
{query}

Generated query:
{generated_query}

Equivalence Score (0-1, with explanation):"""