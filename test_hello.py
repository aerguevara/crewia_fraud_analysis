from crewai_fraud_analysis.crew import AdventureStreakCrew

def test_greeting():
    crew = AdventureStreakCrew().crew_for_chat()
    print("\n--- INICIANDO CREW ---")
    inputs = {"user_input": "hola, muy buenos dias!"}
    result = crew.kickoff(inputs=inputs)
    print("\n--- RESULTADO FINAL ---")
    print(result)

if __name__ == "__main__":
    test_greeting()
