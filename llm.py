from parameters import prompt_schema, classification_prompt, score_prompt
import re

class LLM:
    def __init__(self, model):
        self.model = model
    
    def generate_query(self, question, prompt=prompt_schema, schema=None):
        """
        Generate a SQL query based on the schema and question.
        """
        prompt_completed = prompt.format(question=question, schema=schema)

        print(f"\nprompt: {prompt_completed}\n")
        generated_query = self.model.invoke(prompt_completed)

        return generated_query
    
    def is_correct(self, generated_query, query, classification_prompt=classification_prompt) -> bool:
        """
        Return true if generated query is considered as equivalent to query in terms of result by an orchestrator LLM
        Args:
            - generated_query: SQL generated query
            - query: groundtruth query to compare with
            - classification_prompt: Prompt given to the LLM orchestrator to classify the query as correct or not
        Returns:
            - Bool: True if the query is correct, else False
        """
        pattern = r'\b(yes|no)\b'
        correct = self.model.invoke(classification_prompt.format(query = query, generated_query = generated_query))
        matches = re.findall(pattern, correct, flags=re.IGNORECASE)

        return "Yes" in matches or "yes" in matches

    def equivalence_score(self,generated_query, query, score_prompt=score_prompt) -> bool:
        """
        Return an equivalence score between generated query and a groundtruth query with an orchestrator LLM
        """
        pattern = r"\s*([0-9]*\.?[0-9]+)"
        explanation = self.model.invoke(score_prompt.format(query = query, generated_query = generated_query))
        match = re.search(pattern, explanation, flags=re.IGNORECASE)

        score = 0

        if match:
            score = float(match.group(1))
        
        return score, explanation