from dataclasses import dataclass


@dataclass
class AnalysisPrompt:
    """Template for analysis prompts"""

    ORCHESTRATOR_PROMPT = """
        You have access to a search engine tool. To invoke search, begin by explaining your reasoning for invoking search with the phrase
        "REASON: ", then begin your query with the phrase
        “SEARCH: ”. You may invoke the search tool as many times as needed. Your task is to analyze the
        factuality of the given statement state a score from 0.00 to 1.00, where 0.00 represents definitively false and 1.00 represents definitively true.
        When you have finished conducting all searches, your only message should be "READY". 
        There should be no extra text. You must then wait for the User to specify their desired output format.

        Statement: {statement}

        """ 
    
    GET_VERACITY = """

    "After providing all your analysis steps, summarize your analysis and state a score from 0 to 1, 
    where 0 represents definitively false and 1 represents definitively true, in the following JSON format:\n"
        "{\n"
        '    "veracity_score": <float between 0 and 1>,\n'
        '    "analysis": "<detailed analysis text>"\n'
        "}\n\n"
        "Important formatting rules:\n"
        "1. Provide ONLY the JSON object, no additional text\n"
        "2. Ensure all special characters in the analysis text are properly escaped\n"
        "3. The analysis field should be a single line with newlines represented as \\n\n"
        "4. Do not include any control characters\n"

    """

    IDEAL_PROMPT = """
        After providing all your analysis steps, summarize your analysis and and state “Factuality: ” and a score from 0 to 1, 
        where 0 represents definitively false and 100 represents definitively true. You should begin your summary with the phrase ”Summary: 
    """


    SUMMARIZE_SEARCH ="""Please summarize the searched information for the query. Summarize your findings, 
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
