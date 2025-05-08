from dataclasses import dataclass


@dataclass
class AnalysisPrompt:
    """Template for analysis prompts"""

    ORCHESTRATOR_PROMPT = """
        You have access to a search engine tool. To invoke search, begin by explaining your reasoning for invoking search with the phrase
        "REASON: ", then begin your query with the phrase
        “SEARCH: ”. You may invoke the search tool as many times as needed, but you can only include one search per message. After each search,
        you should wait for the response before proceeding with further searches. Today is {date}. Your task is to analyze the
        factuality of the given statement (for today's date) and state a score from 0 to 100, where 0 represents definitively false and 100 represents definitively true.
        When you have finished conducting all searches, your only message should be "READY".
        There should be no extra text. You must then wait for the User to specify their desired output format.
        "REASON: " and "SEARCH: " should only be used when invoking the search tool and must not appear in any other context.

        Statement: {statement}

        """

    ORCHESTRATOR_PROMPT_FR = """ Vous avez accès à un moteur de recherche. Pour lancer la recherche, commencez par expliquer votre raisonnement avec la phrase
        "REASON : ", puis commencez votre requête par la phrase
        "SEARCH : ". Vous pouvez invoquer le moteur de recherche autant de fois que nécessaire, mais vous pouvez invoquer le moteur de recherche qu'une seule fois par message.
        L'assistant vous donnera les résultats, puis vous pourrez invoquer le moteur de recherche à nouveau. Aujourd’hui, nous sommes le {date}. Votre tâche consiste à analyser la
        véracité de l'affirmation donnée (pour la date d’aujourd’hui) et à indiquer un index de 0 à 100, où 0 représente définitivement faux et 100 représente définitivement vrai.
        Lorsque vous avez terminé d'effectuer toutes les recherches, votre seul message devrait être "PRÊT".
        Il ne doit pas y avoir de texte supplémentaire. Vous devez ensuite attendre que l'utilisateur spécifie le format de sortie souhaité.
        "REASON : " et "SEARCH : " doivent seulement être utilisées lors de l’invocation du moteur de recherche et ne doivent pas apparaître dans d’autres contextes.

        L’affirmation : {statement}

        """

    ORCHESTRATOR_PROMPT_DATE = """
        You have access to a search engine tool. To invoke search, begin by explaining your reasoning for invoking search with the phrase
        "REASON: ", then begin your query with the phrase
        “SEARCH: ”. You must also include a date restriction using the phrase
        "DATE_RESTRICT: ", followed by a specific date or date range in the format YYYY-MM-DD or YYYY-MM-DD to YYYY-MM-DD.
        This helps limit your search to relevant information based on publication date.
        
        You may invoke the search tool as many times as needed, but you can only include one search per message. After each search,
        you should wait for the response before proceeding with further searches. Today is {date}. Your task is to analyze the
        factuality of the given statement (for today's date) and state a score from 0 to 100, where 0 represents definitively false and 100 represents definitively true.
        When you have finished conducting all searches, your only message should be "READY".
        There should be no extra text. You must then wait for the User to specify their desired output format.
        "REASON: ", "SEARCH: ", and "DATE_RESTRICT: " should only be used when invoking the search tool and must not appear in any other context.

        Statement: {statement}

        """

    GET_VERACITY = """

    "After providing all your analysis steps, summarize your analysis and state a score from 0 to 100,
    where 0 represents definitively false and 100 represents definitively true, in the following JSON format:\n"
        "{\n"
        '    "veracity_score": <integer between 0 and 100>,\n'
        '    "analysis": "<detailed analysis text>"\n'
        "}\n\n"
        "Important formatting rules:\n"
        "1. Provide ONLY the JSON object, no additional text\n"
        "2. Ensure all special characters in the analysis text are properly escaped\n"
        "3. The analysis field should be a single line with newlines represented as \\n\n"
        "4. Do not include any control characters\n"

    """

    GET_VERACITY_FR = """

    "Après avoir fourni toutes vos étapes d'analyse, résumez votre analyse et indiquez un score de 0 à 100,
    où 0 représente définitivement faux et 100 représente définitivement vrai, dans le format JSON suivant:\n"
        "{\n"
        '    "veracity_score": <integer entre 0 et 100>,\n'
        '    "analysis": "<résumé de votre analyse>"\n'
        "}\n\n"
        "Règles de formatage importantes:\n"
        "1. Fournissez UNIQUEMENT l'objet JSON, aucun texte supplémentaire\n"
        "2. Assurez-vous que tous les caractères spéciaux dans le texte d'analyse sont correctement retranscrits\n"
        "3. Le champ "analysis" doit être une seule ligne avec des nouvelles lignes représentées par \\n\n"
        "4. N'ajoutez aucune entité de caractère\n"

    """

    IDEAL_PROMPT = """
        After providing all your analysis steps, summarize your analysis and and state “Factuality: ” and a score from 0 to 1,
        where 0 represents definitively false and 100 represents definitively true. You should begin your summary with the phrase ”Summary:
    """

    SUMMARIZE_SEARCH = """Please summarize the searched information for the query. Summarize your findings,
    taking into account the diversity and accuracy of the search results.
    Ensure your analysis is thorough and well-organized.\nQuery: {query}\nSearch results: {res}"""

    CLAIM_ANALYSIS = """Analyze the following claim based on the provided context and sources:

        Claim: {claim_text}

        Context: {context}

        Sources:
        {sources}

        Please provide:
        1. A veracity score (0-1) where 0 is completely false and 1 is completely true
        2. A confidence score (0-1) for your analysis
        3. A detailed step-by-step analysis explaining your reasoning
        4. Key points from the sources that support your analysis

        Format your response as JSON:
        {{
            "veracity_score": float,
            "confidence_score": float,
            "analysis": string,
            "key_points": List[string]
        }}
        """

    CLAIM_ANALYSIS_FRENCH = """I Can't"""

    CLAIM_DETECTION = """Determine if the following message contains a verifiable claim:

        Message: {message}

        If a claim is found, extract and respond with the claim in JSON format:
        {{
            "has_claim": true,
            "claim": "extracted claim",
            "confidence": float
        }}

        If no claim is found, respond with:
        {{
            "has_claim": false,
            "claim": null,
            "confidence": 0.0
        }}
        """
