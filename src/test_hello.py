from crewai_fraud_analysis.crew import CrewaiFraudAnalysis

def test_greeting():
    crew = CrewaiFraudAnalysis().crew_for_chat()
    print("\n--- INICIANDO CREW ---")
    inputs = {"user_input": "hola, muy buenos dias! que tal?"}
    result = crew.kickoff(inputs=inputs)
    print("\n--- RESULTADO FINAL ---")
    print(result)

if __name__ == "__main__":
    test_greeting()
